#!/usr/bin/env python3
"""Evaluate Korean MT-Bench translation validity and category summaries."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mtbench_repro.client import ChatClient  # noqa: E402
from mtbench_repro.schemas import MT_BENCH_CATEGORIES  # noqa: E402
from scripts.translate.back_translate import (  # noqa: E402
    EXPECTED_QUESTION_COUNT,
    EXPECTED_TURN_COUNT,
    prompt_fingerprint as back_translation_prompt_fingerprint,
)


def _ngrams(tokens: List[str], n: int) -> Dict[tuple, int]:
    counts: Dict[tuple, int] = defaultdict(int)
    for i in range(len(tokens) - n + 1):
        counts[tuple(tokens[i : i + n])] += 1
    return dict(counts)

def bleu_score(hypothesis: str, reference: str, max_n: int = 4) -> float:
    hyp_tokens = hypothesis.lower().split()
    ref_tokens = reference.lower().split()
    if len(hyp_tokens) == 0:
        return 0.0
    bp = min(1.0, math.exp(1 - len(ref_tokens) / max(len(hyp_tokens), 1)))
    precisions = []
    for n in range(1, max_n + 1):
        hyp_ngrams = _ngrams(hyp_tokens, n)
        ref_ngrams = _ngrams(ref_tokens, n)
        if not hyp_ngrams:
            precisions.append(0.0)
            continue
        clipped = sum(min(cnt, ref_ngrams.get(gram, 0)) for gram, cnt in hyp_ngrams.items())
        total = sum(hyp_ngrams.values())
        precisions.append(clipped / total if total > 0 else 0.0)
    if any(p == 0 for p in precisions):
        return 0.0
    log_avg = sum(math.log(p) for p in precisions) / max_n
    return bp * math.exp(log_avg)

_SYSTEM_VALIDITY = """\
You are evaluating the quality of a Korean translation of an MT-Bench benchmark item.
You will be given:
1. The original English item.
2. The back-translated English item (produced by translating the Korean back into English).

Your task is to infer whether the Korean translation faithfully preserved the original, by comparing the original and back-translated English.

Evaluate the following three dimensions:
- Semantic preservation: Does the back-translation preserve the original meaning and task intent?
- Difficulty preservation: Does the back-translation preserve the original level of difficulty?
- Constraint preservation: Are all explicit constraints preserved? (e.g., word/character limits, required format, role instructions, numbers, output structure)

Use a 1-5 scale for each:
5 = fully preserved
4 = mostly preserved with only minor wording differences
3 = partially preserved; may have measurable impact on model responses
2 = important information or constraints are changed
1 = substantially different from the original

Set needs_manual_check to true if ANY of the following apply:
- Any dimension score is 3 or below
- A constraint (number, format, role, length limit) is missing or changed
- The task type appears to have changed (e.g., correction task became a generation task)
- The back-translation performs the task instead of describing it

Return JSON only, with no additional text:
{
  "semantic_preservation": 1-5,
  "difficulty_preservation": 1-5,
  "constraint_preservation": 1-5,
  "overall_score": 1-5,
  "issue_summary": "one sentence describing the main issue, or 'no issue' if fully preserved",
  "needs_manual_check": true or false
}\
"""

_VALIDITY_USER_TEMPLATE = (
    "Original English item:\n{original}\n\n"
    "Back-translated English item:\n{back_translated}"
)

_FAIL_RESULT = {
    "semantic_preservation": -1,
    "difficulty_preservation": -1,
    "constraint_preservation": -1,
    "overall_score": -1,
    "issue_summary": "parse error",
    "needs_manual_check": True,
    "parse_status": "invalid: unspecified parse error",
}

_SCORE_FIELDS = (
    "semantic_preservation",
    "difficulty_preservation",
    "constraint_preservation",
    "overall_score",
)
_RESPONSE_FIELDS = set(_SCORE_FIELDS) | {"issue_summary", "needs_manual_check"}


def _invalid_score_result(reason: str, response: str = "") -> dict:
    detail = reason.strip() or "unspecified parse error"
    excerpt = response.strip().replace("\n", " ")[:100]
    if excerpt:
        detail = f"{detail}; response={excerpt!r}"
    return {
        **_FAIL_RESULT,
        "issue_summary": detail[:300],
        "parse_status": f"invalid: {reason}"[:300],
    }

def parse_validity_response(response: str) -> dict:
    """Parse and strictly validate the judge's JSON response."""
    text = response.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return _invalid_score_result(
            f"JSON decode error at position {exc.pos}: {exc.msg}", response
        )

    if not isinstance(data, dict):
        return _invalid_score_result("top-level JSON value must be an object", response)

    missing = sorted(_RESPONSE_FIELDS - set(data))
    extra = sorted(set(data) - _RESPONSE_FIELDS)
    if missing or extra:
        details = []
        if missing:
            details.append(f"missing fields {missing}")
        if extra:
            details.append(f"unexpected fields {extra}")
        return _invalid_score_result("; ".join(details), response)

    for field in _SCORE_FIELDS:
        value = data[field]
        if type(value) is not int or not 1 <= value <= 5:
            return _invalid_score_result(
                f"{field} must be an integer from 1 through 5 (booleans excluded)",
                response,
            )

    if type(data["needs_manual_check"]) is not bool:
        return _invalid_score_result(
            "needs_manual_check must be a JSON boolean", response
        )
    if not isinstance(data["issue_summary"], str):
        return _invalid_score_result("issue_summary must be a string", response)

    low_score = any(data[field] <= 3 for field in _SCORE_FIELDS)
    supplied_manual_check = data["needs_manual_check"]
    needs_manual_check = supplied_manual_check or low_score
    if low_score and not supplied_manual_check:
        parse_status = "ok: low score forced needs_manual_check=true"
    elif low_score:
        parse_status = "ok: low score"
    else:
        parse_status = "ok"

    return {
        **{field: data[field] for field in _SCORE_FIELDS},
        "issue_summary": data["issue_summary"][:300],
        "needs_manual_check": needs_manual_check,
        "parse_status": parse_status,
    }

def llm_validity_score(
    client: ChatClient,
    original: str,
    back_translated: str,
    model: str,
    sleep: float = 0.3,
) -> dict:
    """3차원 번역 품질 점수 반환. 실패 시 _FAIL_RESULT."""
    if client._mock:
        return {
            "semantic_preservation": 4,
            "difficulty_preservation": 4,
            "constraint_preservation": 4,
            "overall_score": 4,
            "issue_summary": "mock: mostly preserved.",
            "needs_manual_check": False,
            "parse_status": "ok: mock",
        }

    prompt = _VALIDITY_USER_TEMPLATE.format(
        original=original,
        back_translated=back_translated,
    )
    messages = [
        {"role": "system", "content": _SYSTEM_VALIDITY},
        {"role": "user", "content": prompt},
    ]
    response = client.chat(messages, model=model, temperature=0.0, max_tokens=300)
    if sleep > 0:
        time.sleep(sleep)

    return parse_validity_response(response)

def load_jsonl_by_id(path: str) -> Dict[int, dict]:
    result: Dict[int, dict] = {}
    with open(path, encoding="utf-8") as f:
        for line_number, line in enumerate(f, 1):
            line = line.strip()
            if line:
                try:
                    obj = json.loads(line)
                    question_id = obj["question_id"]
                except (json.JSONDecodeError, KeyError, TypeError) as exc:
                    raise ValueError(f"{path}:{line_number}: invalid JSONL record") from exc
                if not isinstance(obj, dict):
                    raise ValueError(f"{path}:{line_number}: record must be an object")
                if isinstance(question_id, bool) or not isinstance(question_id, int):
                    raise ValueError(
                        f"{path}:{line_number}: question_id must be an integer"
                    )
                if question_id in result:
                    raise ValueError(f"{path}: duplicate question_id {question_id}")
                result[question_id] = obj
    return result

def validate_input_coverage(
    original_by_id: Dict[int, dict],
    korean_by_id: Dict[int, dict],
    back_by_id: Dict[int, dict],
) -> list[int]:
    """Require identical 80-question ID sets and exactly two turns per item."""
    datasets = {
        "original": original_by_id,
        "korean source": korean_by_id,
        "back translation": back_by_id,
    }
    for label, records in datasets.items():
        if len(records) != EXPECTED_QUESTION_COUNT:
            raise ValueError(
                f"{label}: expected exactly {EXPECTED_QUESTION_COUNT} unique "
                f"question IDs, found {len(records)}"
            )

    expected_ids = set(original_by_id)
    for label, records in datasets.items():
        ids = set(records)
        if ids != expected_ids:
            missing = sorted(expected_ids - ids)
            extra = sorted(ids - expected_ids)
            raise ValueError(
                f"{label}: question IDs differ from original "
                f"(missing={missing[:10]}, extra={extra[:10]})"
            )

        for question_id, record in records.items():
            turns = record.get("turns")
            if (
                not isinstance(turns, list)
                or len(turns) != EXPECTED_TURN_COUNT
                or any(not isinstance(turn, str) or not turn.strip() for turn in turns)
            ):
                raise ValueError(
                    f"{label}: question_id {question_id} must have exactly "
                    f"{EXPECTED_TURN_COUNT} non-empty string turns"
                )

    for question_id in expected_ids:
        expected_category = original_by_id[question_id].get("category")
        for label, records in (
            ("korean source", korean_by_id),
            ("back translation", back_by_id),
        ):
            if records[question_id].get("category") != expected_category:
                raise ValueError(
                    f"{label}: category mismatch for question_id {question_id}"
                )

    return sorted(expected_ids)

def record_fingerprint(record: dict) -> str:
    """Hash the fields that materially determine a validity judgment."""
    payload = {
        "question_id": record.get("question_id"),
        "category": record.get("category"),
        "turns": record.get("turns"),
        "reference": record.get("reference"),
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

def validity_prompt_fingerprint() -> str:
    payload = json.dumps(
        {
            "protocol": "translation-validity-v2",
            "system": _SYSTEM_VALIDITY,
            "user_template": _VALIDITY_USER_TEMPLATE,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()

def back_translation_record_is_current(
    record: dict, korean: dict, execution_mode: str
) -> bool:
    """Check source, exact prompt protocol, and live/mock provenance."""
    return (
        record.get("source_sha256") == record_fingerprint(korean)
        and record.get("back_translation_prompt_sha256")
        == back_translation_prompt_fingerprint()
        and (
            execution_mode == "mock"
            or record.get("back_translation_mode") == "live"
        )
    )

def validity_record_is_current(
    row: dict,
    original: dict,
    korean: dict,
    back_translation: dict,
    provider: str,
    model: str,
    execution_mode: str,
) -> bool:
    expected_parse_status = {
        "mock": "ok: mock",
        "bleu_only": "not run: BLEU only",
    }.get(execution_mode)
    statuses = [row.get("parse_status_turn1"), row.get("parse_status_turn2")]
    live_statuses = {
        "ok",
        "ok: low score",
        "ok: low score forced needs_manual_check=true",
    }
    parse_is_current = (
        statuses == [expected_parse_status, expected_parse_status]
        if expected_parse_status is not None
        else all(status in live_statuses for status in statuses)
    )
    if not (
        row.get("original_sha256") == record_fingerprint(original)
        and row.get("korean_source_sha256") == record_fingerprint(korean)
        and row.get("back_translation_sha256")
        == record_fingerprint(back_translation)
        and row.get("validity_provider") == provider
        and row.get("validity_model") == model
        and row.get("validity_mode") == execution_mode
        and row.get("validity_prompt_sha256") == validity_prompt_fingerprint()
        and parse_is_current
        and row.get("category") == original.get("category")
    ):
        return False

    try:
        if isinstance(row.get("question_id"), bool):
            return False
        if int(row.get("question_id")) != original.get("question_id"):
            return False
    except (TypeError, ValueError):
        return False

    def finite_number(value: object) -> float | None:
        if isinstance(value, bool) or value is None or value == "":
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if math.isfinite(parsed) else None

    def exact_score(value: object) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            parsed = value
        elif isinstance(value, str) and re.fullmatch(r"[1-5]", value):
            parsed = int(value)
        else:
            return None
        return parsed if 1 <= parsed <= 5 else None

    manual_value = row.get("needs_manual_check")
    if type(manual_value) is bool:
        needs_manual_check = manual_value
    elif manual_value in {"True", "False"}:
        needs_manual_check = manual_value == "True"
    else:
        return False

    bleu_values = [
        finite_number(row.get("bleu_turn1")),
        finite_number(row.get("bleu_turn2")),
        finite_number(row.get("bleu_avg")),
    ]
    if any(value is None or not 0.0 <= value <= 1.0 for value in bleu_values):
        return False
    assert all(value is not None for value in bleu_values)
    if not math.isclose(
        bleu_values[2],
        round((bleu_values[0] + bleu_values[1]) / 2, 4),
        abs_tol=1e-9,
    ):
        return False

    if execution_mode == "bleu_only":
        for dimension in ("semantic", "difficulty", "constraint", "overall"):
            if row.get(f"{dimension}_turn1") not in {-1, "-1"}:
                return False
            if row.get(f"{dimension}_turn2") not in {-1, "-1"}:
                return False
            if row.get(f"{dimension}_avg") not in {None, ""}:
                return False
        return not needs_manual_check

    all_scores: list[int] = []
    for dimension in ("semantic", "difficulty", "constraint", "overall"):
        turn_scores = [
            exact_score(row.get(f"{dimension}_turn1")),
            exact_score(row.get(f"{dimension}_turn2")),
        ]
        average = finite_number(row.get(f"{dimension}_avg"))
        if any(score is None for score in turn_scores) or average is None:
            return False
        assert turn_scores[0] is not None and turn_scores[1] is not None
        if not 1.0 <= average <= 5.0 or not math.isclose(
            average,
            round((turn_scores[0] + turn_scores[1]) / 2, 2),
            abs_tol=1e-9,
        ):
            return False
        all_scores.extend(turn_scores)

    if any(score <= 3 for score in all_scores) and not needs_manual_check:
        return False
    return all(isinstance(row.get(field), str) for field in (
        "issue_summary_turn1",
        "issue_summary_turn2",
    ))

def write_csv_atomic(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    """Write a complete CSV to a same-directory temp file and atomically replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)

def spearman_rho(xs: List[float], ys: List[float]) -> float:
    n = len(xs)
    if n < 3:
        return float("nan")

    def rank(vals: List[float]) -> List[float]:
        sorted_vals = sorted(enumerate(vals), key=lambda x: x[1])
        ranks = [0.0] * n
        for r, (i, _) in enumerate(sorted_vals, 1):
            ranks[i] = float(r)
        return ranks

    rx = rank(xs)
    ry = rank(ys)
    d2 = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    return 1 - 6 * d2 / (n * (n * n - 1))

FIELDNAMES = [
    "question_id", "category",
    "original_sha256", "korean_source_sha256", "back_translation_sha256",
    "validity_provider", "validity_model",
    "validity_prompt_sha256", "validity_mode",
    "bleu_turn1", "bleu_turn2", "bleu_avg",
    "semantic_turn1", "semantic_turn2", "semantic_avg",
    "difficulty_turn1", "difficulty_turn2", "difficulty_avg",
    "constraint_turn1", "constraint_turn2", "constraint_avg",
    "overall_turn1", "overall_turn2", "overall_avg",
    "needs_manual_check",
    "parse_status_turn1", "parse_status_turn2",
    "issue_summary_turn1", "issue_summary_turn2",
]

CAT_FIELDNAMES = [
    "category", "n",
    "bleu_mean",
    "semantic_mean", "difficulty_mean", "constraint_mean", "overall_mean",
    "needs_manual_check_count",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="번역 validity 검증 (3차원)")
    parser.add_argument("--original",
        default=str(PROJECT_ROOT / "data" / "en" / "questions.jsonl"))
    parser.add_argument("--back-translated",
        default=str(PROJECT_ROOT / "data" / "ko" / "questions_back.jsonl"))
    parser.add_argument("--korean-source",
        default=str(PROJECT_ROOT / "data" / "ko" / "questions.jsonl"))
    parser.add_argument("--output-csv",
        default=str(PROJECT_ROOT / "runs" / "translation_validity" / "scores.csv"))
    parser.add_argument("--output-category-csv",
        default=str(PROJECT_ROOT / "runs" / "translation_validity" / "per_category.csv"))
    parser.add_argument("--provider", choices=["anthropic", "openai"], default="openai")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--sleep", type=float, default=0.3)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--skip-llm-score", action="store_true",
                        help="LLM 점수 생략 (BLEU만 계산)")
    parser.add_argument("--no-resume", action="store_true",
                        help="기존 결과 무시하고 처음부터 재실행")
    args = parser.parse_args()

    for label, path in [
        ("원본", args.original),
        ("한국어 원문", args.korean_source),
        ("역번역", args.back_translated),
    ]:
        if not Path(path).exists():
            print(f"[오류] {label} 파일 없음: {path}")
            sys.exit(1)

    original_by_id = load_jsonl_by_id(args.original)
    korean_by_id = load_jsonl_by_id(args.korean_source)
    back_by_id = load_jsonl_by_id(args.back_translated)
    try:
        question_ids = validate_input_coverage(
            original_by_id, korean_by_id, back_by_id
        )
    except ValueError as exc:
        print(f"[오류] 입력 coverage 검증 실패: {exc}")
        raise SystemExit(1) from exc
    print(f"[검증] 비교 가능 문항: {len(question_ids)}개")
    execution_mode = (
        "mock" if args.mock else ("bleu_only" if args.skip_llm_score else "live")
    )

    stale_back_translations = [
        qid
        for qid in question_ids
        if not back_translation_record_is_current(
            back_by_id[qid], korean_by_id[qid], execution_mode
        )
    ]
    if stale_back_translations:
        preview = stale_back_translations[:10]
        print(
            "[오류] 현재 한국어 source/prompt와 일치하지 않는 역번역: "
            f"{preview}{' ...' if len(stale_back_translations) > 10 else ''}"
        )
        print("  back_translate.py로 해당 문항을 먼저 다시 생성하세요.")
        sys.exit(1)

    if args.mock or args.skip_llm_score:
        client = ChatClient.mock()
    else:
        base_url = (
            "https://api.anthropic.com"
            if args.provider == "anthropic"
            else "https://api.openai.com/v1"
        )
        client = ChatClient(
            api_key=args.api_key,
            base_url=base_url,
            default_model=args.model,
            provider=args.provider,
        )

    output_path = Path(args.output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows_by_id: Dict[int, dict] = {}
    done_ids: set = set()

    if not args.no_resume and output_path.exists():
        with open(output_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            existing_fields = reader.fieldnames or []
            required_resume_fields = {
                "semantic_turn1",
                "original_sha256",
                "korean_source_sha256",
                "back_translation_sha256",
                "validity_provider",
                "validity_model",
                "validity_prompt_sha256",
                "validity_mode",
                "parse_status_turn1",
                "parse_status_turn2",
            }
            if required_resume_fields.issubset(existing_fields):
                seen_existing_ids: set[int] = set()
                for row in reader:
                    try:
                        qid = int(row["question_id"])
                    except (KeyError, TypeError, ValueError) as exc:
                        raise ValueError(
                            f"{output_path}: invalid question_id in resume CSV"
                        ) from exc
                    if qid in seen_existing_ids:
                        raise ValueError(
                            f"{output_path}: duplicate question_id {qid}"
                        )
                    seen_existing_ids.add(qid)
                    if qid not in original_by_id or qid not in back_by_id:
                        continue
                    if validity_record_is_current(
                        row,
                        original_by_id[qid],
                        korean_by_id[qid],
                        back_by_id[qid],
                        args.provider,
                        args.model,
                        execution_mode,
                    ):
                        rows_by_id[qid] = row
                        done_ids.add(qid)
                if done_ids:
                    print(f"[resume] 이미 처리된 {len(done_ids)}개 건너뜀")
            else:
                print("[resume] 기존 CSV가 구버전 형식 — 전체 재실행합니다.")

    total = len(question_ids)
    failed_ids: list[int] = []
    invalid_score_ids: list[int] = []
    for i, qid in enumerate(question_ids, 1):
        if qid in done_ids:
            continue

        orig = original_by_id[qid]
        back = back_by_id[qid]
        category = orig.get("category", "unknown")

        turn_bleus = []
        turn_scores = []

        try:
            for t_idx in range(EXPECTED_TURN_COUNT):
                orig_text = orig["turns"][t_idx]
                back_text = back["turns"][t_idx]

                bleu = bleu_score(back_text, orig_text)
                turn_bleus.append(bleu)

                if not args.skip_llm_score:
                    sc = llm_validity_score(
                        client, orig_text, back_text, args.model, args.sleep
                    )
                else:
                    sc = {key: -1 for key in _SCORE_FIELDS}
                    sc["issue_summary"] = ""
                    sc["needs_manual_check"] = False
                    sc["parse_status"] = "not run: BLEU only"
                turn_scores.append(sc)
        except Exception as exc:
            failed_ids.append(qid)
            print(f"  [{i}/{total}] q{qid} ({category}) FAIL ({exc})")
            if args.no_resume:
                break
            continue

        if any(
            not str(score.get("parse_status", "")).startswith("ok")
            for score in turn_scores
        ) and not args.skip_llm_score:
            invalid_score_ids.append(qid)

        avg_bleu = sum(turn_bleus) / len(turn_bleus) if turn_bleus else 0.0

        def _avg(dim: str) -> str:
            valid = [s[dim] for s in turn_scores if s[dim] > 0]
            return str(round(sum(valid) / len(valid), 2)) if valid else ""

        needs_check = any(s["needs_manual_check"] for s in turn_scores)

        row = {
            "question_id": qid,
            "category": category,
            "original_sha256": record_fingerprint(orig),
            "korean_source_sha256": record_fingerprint(korean_by_id[qid]),
            "back_translation_sha256": record_fingerprint(back),
            "validity_provider": args.provider,
            "validity_model": args.model,
            "validity_prompt_sha256": validity_prompt_fingerprint(),
            "validity_mode": execution_mode,
            "bleu_turn1": round(turn_bleus[0], 4) if len(turn_bleus) > 0 else "",
            "bleu_turn2": round(turn_bleus[1], 4) if len(turn_bleus) > 1 else "",
            "bleu_avg": round(avg_bleu, 4),
            "semantic_turn1": turn_scores[0]["semantic_preservation"] if len(turn_scores) > 0 else "",
            "semantic_turn2": turn_scores[1]["semantic_preservation"] if len(turn_scores) > 1 else "",
            "semantic_avg": _avg("semantic_preservation"),
            "difficulty_turn1": turn_scores[0]["difficulty_preservation"] if len(turn_scores) > 0 else "",
            "difficulty_turn2": turn_scores[1]["difficulty_preservation"] if len(turn_scores) > 1 else "",
            "difficulty_avg": _avg("difficulty_preservation"),
            "constraint_turn1": turn_scores[0]["constraint_preservation"] if len(turn_scores) > 0 else "",
            "constraint_turn2": turn_scores[1]["constraint_preservation"] if len(turn_scores) > 1 else "",
            "constraint_avg": _avg("constraint_preservation"),
            "overall_turn1": turn_scores[0]["overall_score"] if len(turn_scores) > 0 else "",
            "overall_turn2": turn_scores[1]["overall_score"] if len(turn_scores) > 1 else "",
            "overall_avg": _avg("overall_score"),
            "needs_manual_check": needs_check,
            "parse_status_turn1": turn_scores[0]["parse_status"],
            "parse_status_turn2": turn_scores[1]["parse_status"],
            "issue_summary_turn1": turn_scores[0]["issue_summary"] if len(turn_scores) > 0 else "",
            "issue_summary_turn2": turn_scores[1]["issue_summary"] if len(turn_scores) > 1 else "",
        }
        rows_by_id[qid] = row

        sem = row["semantic_avg"]
        diff = row["difficulty_avg"]
        con = row["constraint_avg"]
        ov = row["overall_avg"]
        flag = " ⚠" if needs_check else ""
        print(
            f"  [{i}/{total}] q{qid} ({category}) "
            f"BLEU={avg_bleu:.3f} sem={sem} diff={diff} con={con} overall={ov}{flag}"
        )

        if not args.no_resume:
            checkpoint_rows = [rows_by_id[item_id] for item_id in sorted(rows_by_id)]
            write_csv_atomic(output_path, FIELDNAMES, checkpoint_rows)
        elif qid in invalid_score_ids:
            break

    missing_result_ids = sorted(set(question_ids) - set(rows_by_id))
    if failed_ids or invalid_score_ids or missing_result_ids:
        print(
            "\n[오류] validity 검증을 완료하지 못했습니다: "
            f"API/실행 실패={failed_ids[:10]}, "
            f"점수 JSON 무효={invalid_score_ids[:10]}, "
            f"결과 누락={missing_result_ids[:10]}"
        )
        print("  정확히 80문항×2턴이 모두 성공해야 성공으로 종료합니다.")
        raise SystemExit(1)

    all_rows = [rows_by_id[qid] for qid in sorted(rows_by_id)]
    write_csv_atomic(output_path, FIELDNAMES, all_rows)
    print(f"\n[저장] {output_path}")

    cat_rows: Dict[str, list] = defaultdict(list)
    for row in all_rows:
        cat_rows[row["category"]].append(row)

    cat_summary = []
    for cat in MT_BENCH_CATEGORIES:
        rows = cat_rows.get(cat, [])
        if not rows:
            continue

        def cat_mean(field: str) -> str:
            vals = [float(r[field]) for r in rows if r[field] not in ("", "-1", -1)]
            return str(round(sum(vals) / len(vals), 2)) if vals else ""

        bleus = [float(r["bleu_avg"]) for r in rows if r["bleu_avg"] != ""]
        check_count = sum(1 for r in rows if str(r["needs_manual_check"]) == "True")
        cat_summary.append({
            "category": cat,
            "n": len(rows),
            "bleu_mean": round(sum(bleus) / len(bleus), 4) if bleus else "",
            "semantic_mean": cat_mean("semantic_avg"),
            "difficulty_mean": cat_mean("difficulty_avg"),
            "constraint_mean": cat_mean("constraint_avg"),
            "overall_mean": cat_mean("overall_avg"),
            "needs_manual_check_count": check_count,
        })

    cat_output = Path(args.output_category_csv)
    write_csv_atomic(cat_output, CAT_FIELDNAMES, cat_summary)
    print(f"[저장] {cat_output}")

    print("\n" + "=" * 75)
    print(" 번역 Validity 요약 (3차원)")
    print("=" * 75)
    print(f"{'카테고리':<14} {'n':>3}  {'BLEU':>6}  {'Semantic':>8}  {'Difficulty':>10}  {'Constraint':>10}  {'Overall':>7}  {'⚠':>3}")
    print("-" * 75)
    for s in cat_summary:
        print(
            f"{s['category']:<14} {s['n']:>3}  "
            f"{str(s['bleu_mean']):>6}  "
            f"{str(s['semantic_mean']):>8}  "
            f"{str(s['difficulty_mean']):>10}  "
            f"{str(s['constraint_mean']):>10}  "
            f"{str(s['overall_mean']):>7}  "
            f"{s['needs_manual_check_count']:>3}"
        )
    print("-" * 75)

    def global_mean(field: str) -> str:
        vals = [float(r[field]) for r in all_rows if r.get(field) not in ("", "-1", -1, None)]
        return f"{sum(vals)/len(vals):.2f}" if vals else "N/A"

    all_bleus = [float(r["bleu_avg"]) for r in all_rows if r["bleu_avg"] != ""]
    total_check = sum(1 for r in all_rows if str(r.get("needs_manual_check")) == "True")
    bleu_mean = f"{sum(all_bleus)/len(all_bleus):.4f}" if all_bleus else "N/A"
    print(
        f"{'전체 평균':<14} {len(all_rows):>3}  "
        f"{bleu_mean:>6}  "
        f"{global_mean('semantic_avg'):>8}  "
        f"{global_mean('difficulty_avg'):>10}  "
        f"{global_mean('constraint_avg'):>10}  "
        f"{global_mean('overall_avg'):>7}  "
        f"{total_check:>3}"
    )
    print("=" * 75)
    print(f"\n수동 확인 필요 문항: {total_check}개 (needs_manual_check=True)")

if __name__ == "__main__":
    main()
