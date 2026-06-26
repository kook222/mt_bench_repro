#!/usr/bin/env python3
"""
scripts/analysis/analyze_translation_validity.py

MT-Bench 한국어 번역 validity 검증.

검증 항목:
  [검증 1] Back-translation 기반 자동 품질 점수
    - BLEU score (단어 n-gram 오버랩)
    - LLM 3차원 점수 (semantic / difficulty / constraint preservation, 1~5)
      + overall score + needs_manual_check
    - 카테고리별 분포

  [검증 2] 카테고리별 집계

사용법:
    export PYTHONPATH=src
    python3 scripts/analysis/analyze_translation_validity.py \\
        --provider openai --model gpt-4o-mini --api-key $OPENAI_API_KEY

    # mock 테스트 (API 없이)
    python3 scripts/analysis/analyze_translation_validity.py --mock

출력:
    data/ko/results/results_translation_validity.csv
    data/ko/results/results_translation_validity_per_category.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mtbench_repro.client import ChatClient
from mtbench_repro.schemas import MT_BENCH_CATEGORIES


# ── BLEU 계산 ────────────────────────────────────────────────────────────────

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


# ── LLM 3차원 번역 품질 점수 ──────────────────────────────────────────────────

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

_FAIL_RESULT = {
    "semantic_preservation": -1,
    "difficulty_preservation": -1,
    "constraint_preservation": -1,
    "overall_score": -1,
    "issue_summary": "parse error",
    "needs_manual_check": True,
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
        }

    prompt = (
        f"Original English item:\n{original}\n\n"
        f"Back-translated English item:\n{back_translated}"
    )
    messages = [
        {"role": "system", "content": _SYSTEM_VALIDITY},
        {"role": "user", "content": prompt},
    ]
    response = client.chat(messages, model=model, temperature=0.0, max_tokens=300)
    if sleep > 0:
        time.sleep(sleep)

    # JSON 파싱
    try:
        # 마크다운 코드블록 제거
        text = re.sub(r"```json\s*|\s*```", "", response.strip())
        # 첫 번째 { ... } 블록 추출
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return {**_FAIL_RESULT, "issue_summary": f"no JSON: {response[:100]}"}
        data = json.loads(m.group())
        return {
            "semantic_preservation": int(data.get("semantic_preservation", -1)),
            "difficulty_preservation": int(data.get("difficulty_preservation", -1)),
            "constraint_preservation": int(data.get("constraint_preservation", -1)),
            "overall_score": int(data.get("overall_score", -1)),
            "issue_summary": str(data.get("issue_summary", ""))[:300],
            "needs_manual_check": bool(data.get("needs_manual_check", False)),
        }
    except Exception as e:
        return {**_FAIL_RESULT, "issue_summary": f"parse error: {e} / {response[:100]}"}


# ── 데이터 로드 ───────────────────────────────────────────────────────────────

def load_jsonl_by_id(path: str) -> Dict[int, dict]:
    result = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                obj = json.loads(line)
                result[obj["question_id"]] = obj
    return result


# ── Spearman ρ ────────────────────────────────────────────────────────────────

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


# ── CSV 필드 ──────────────────────────────────────────────────────────────────

FIELDNAMES = [
    "question_id", "category",
    "bleu_turn1", "bleu_turn2", "bleu_avg",
    "semantic_turn1", "semantic_turn2", "semantic_avg",
    "difficulty_turn1", "difficulty_turn2", "difficulty_avg",
    "constraint_turn1", "constraint_turn2", "constraint_avg",
    "overall_turn1", "overall_turn2", "overall_avg",
    "needs_manual_check",
    "issue_summary_turn1", "issue_summary_turn2",
]

CAT_FIELDNAMES = [
    "category", "n",
    "bleu_mean",
    "semantic_mean", "difficulty_mean", "constraint_mean", "overall_mean",
    "needs_manual_check_count",
]


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="번역 validity 검증 (3차원)")
    parser.add_argument("--original",
        default=str(PROJECT_ROOT / "data" / "en" / "questions.jsonl"))
    parser.add_argument("--back-translated",
        default=str(PROJECT_ROOT / "data" / "ko" / "questions_back.jsonl"))
    parser.add_argument("--output-csv",
        default=str(PROJECT_ROOT / "data" / "ko" / "results" / "results_translation_validity.csv"))
    parser.add_argument("--output-category-csv",
        default=str(PROJECT_ROOT / "data" / "ko" / "results" / "results_translation_validity_per_category.csv"))
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

    # 파일 존재 확인
    for label, path in [
        ("원본", args.original),
        ("역번역", args.back_translated),
    ]:
        if not Path(path).exists():
            print(f"[오류] {label} 파일 없음: {path}")
            sys.exit(1)

    original_by_id = load_jsonl_by_id(args.original)
    back_by_id = load_jsonl_by_id(args.back_translated)
    common_ids = sorted(set(original_by_id) & set(back_by_id))
    print(f"[검증] 비교 가능 문항: {len(common_ids)}개")

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

    # resume: 새 필드 포함 여부 확인 후 호환 가능한 것만 로드
    output_path = Path(args.output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows_by_id: Dict[int, dict] = {}
    done_ids: set = set()

    if not args.no_resume and output_path.exists():
        with open(output_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            existing_fields = reader.fieldnames or []
            # 새 3차원 필드 포함 여부 확인
            if "semantic_turn1" in existing_fields:
                for row in reader:
                    qid = int(row["question_id"])
                    rows_by_id[qid] = row
                    done_ids.add(qid)
                if done_ids:
                    print(f"[resume] 이미 처리된 {len(done_ids)}개 건너뜀")
            else:
                print("[resume] 기존 CSV가 구버전 형식 — 전체 재실행합니다.")

    # ── 검증: Back-translation BLEU + 3차원 LLM score ────────────────────────
    total = len(common_ids)
    for i, qid in enumerate(common_ids, 1):
        if qid in done_ids:
            continue

        orig = original_by_id[qid]
        back = back_by_id[qid]
        category = orig.get("category", "unknown")

        turn_bleus = []
        turn_scores = []  # 각 턴의 dict

        for t_idx in range(min(len(orig["turns"]), len(back["turns"]))):
            orig_text = orig["turns"][t_idx]
            back_text = back["turns"][t_idx]

            bleu = bleu_score(back_text, orig_text)
            turn_bleus.append(bleu)

            if not args.skip_llm_score:
                sc = llm_validity_score(client, orig_text, back_text, args.model, args.sleep)
            else:
                sc = {k: -1 for k in ["semantic_preservation", "difficulty_preservation",
                                       "constraint_preservation", "overall_score"]}
                sc["issue_summary"] = ""
                sc["needs_manual_check"] = False
            turn_scores.append(sc)

        avg_bleu = sum(turn_bleus) / len(turn_bleus) if turn_bleus else 0.0

        def _avg(dim: str) -> str:
            valid = [s[dim] for s in turn_scores if s[dim] > 0]
            return str(round(sum(valid) / len(valid), 2)) if valid else ""

        needs_check = any(s["needs_manual_check"] for s in turn_scores)

        row = {
            "question_id": qid,
            "category": category,
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

        # append to CSV incrementally (crash-safe)
        write_header = not output_path.exists() or (i == 1 and not done_ids)
        with open(str(output_path), "a" if not write_header else "w",
                  newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            if write_header:
                writer.writeheader()
            writer.writerow(row)

    # ── 전체 CSV 재정렬 저장 ──────────────────────────────────────────────────
    all_rows = [rows_by_id[qid] for qid in sorted(rows_by_id)]
    with open(str(output_path), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"\n[저장] {output_path}")

    # ── 카테고리별 집계 ───────────────────────────────────────────────────────
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
    with open(str(cat_output), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CAT_FIELDNAMES)
        writer.writeheader()
        writer.writerows(cat_summary)
    print(f"[저장] {cat_output}")

    # ── 요약 출력 ─────────────────────────────────────────────────────────────
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
