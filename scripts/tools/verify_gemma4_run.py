#!/usr/bin/env python3
"""Verify complete EN/KO Gemma 4 judge outputs and write an audit summary."""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from mtbench_repro.io_utils import load_questions  # noqa: E402
from mtbench_repro.schemas import REFERENCE_GUIDED_CATEGORIES  # noqa: E402


EVAL_MODELS = (
    "Llama-3.1-8B-Instruct",
    "EEVE-Korean-Instruct-10.8B",
    "EXAONE-3.5-7.8B-Instruct",
    "gemma-2-9b-it",
    "Mistral-7B-Instruct-v0.3",
    "Phi-3.5-mini-Instruct",
)
JUDGE_ID = "Gemma-4-12B-it"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ValueError(f"missing output file: {path}")
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON at {path}:{line_number}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"expected JSON object at {path}:{line_number}")
            records.append(value)
    return records


def require_exact_question_ids(
    records: list[dict[str, Any]], expected_ids: set[int], path: Path
) -> None:
    ids = [record.get("question_id") for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate question_id in {path}")
    if set(ids) != expected_ids:
        missing = sorted(expected_ids - set(ids))
        unexpected = sorted(set(ids) - expected_ids)
        raise ValueError(
            f"question coverage mismatch in {path}: "
            f"missing={missing}, unexpected={unexpected}"
        )
    for record in records:
        if record.get("judge_id") != JUDGE_ID:
            raise ValueError(f"unexpected judge_id in {path}: {record.get('judge_id')}")
        if not record.get("input_sha256"):
            raise ValueError(f"missing input_sha256 in {path}")


def verify_language(run_root: Path, language: str) -> dict[str, Any]:
    questions = load_questions(str(ROOT / "data" / language / "questions.jsonl"))
    all_ids = {question.question_id for question in questions}
    reference_ids = {
        question.question_id
        for question in questions
        if question.category in REFERENCE_GUIDED_CATEGORIES
        and question.reference is not None
    }
    judge_dir = run_root / language / "judgments" / "gemma4" / "judge_12B"

    single_records = 0
    single_parse_failures = 0
    for model in EVAL_MODELS:
        path = judge_dir / "single_grade" / f"{model}.jsonl"
        records = read_jsonl(path)
        require_exact_question_ids(records, all_ids, path)
        if any(record.get("model_id") != model for record in records):
            raise ValueError(f"model_id mismatch in {path}")
        single_records += len(records)
        single_parse_failures += sum(
            record.get(field) == -1
            for record in records
            for field in ("score_turn1", "score_turn2")
        )

    pairwise_records = 0
    pairwise_parse_failures = 0
    inconsistent_records = 0
    for model_a, model_b in itertools.combinations(EVAL_MODELS, 2):
        path = judge_dir / "pairwise" / f"{model_a}_vs_{model_b}.jsonl"
        records = read_jsonl(path)
        require_exact_question_ids(records, all_ids, path)
        for record in records:
            if record.get("model_a") != model_a or record.get("model_b") != model_b:
                raise ValueError(f"model pair mismatch in {path}")
            pairwise_parse_failures += sum(
                record.get(field) == "error"
                for field in ("winner_ab", "winner_ba")
            )
            inconsistent_records += record.get("winner") == "inconsistent"
        pairwise_records += len(records)

    reference_records = 0
    reference_parse_failures = 0
    for model in EVAL_MODELS:
        path = judge_dir / "single_grade_ref" / f"{model}.jsonl"
        records = read_jsonl(path)
        require_exact_question_ids(records, reference_ids, path)
        if any(record.get("model_id") != model for record in records):
            raise ValueError(f"model_id mismatch in {path}")
        reference_records += len(records)
        reference_parse_failures += sum(
            record.get("score_turn2") == -1 for record in records
        )

    expected_single = len(EVAL_MODELS) * len(all_ids)
    expected_pairwise = len(tuple(itertools.combinations(EVAL_MODELS, 2))) * len(all_ids)
    expected_reference = len(EVAL_MODELS) * len(reference_ids)
    return {
        "language": language,
        "judge_id": JUDGE_ID,
        "questions": len(all_ids),
        "reference_questions": len(reference_ids),
        "single_records": single_records,
        "expected_single_records": expected_single,
        "single_parse_failures": single_parse_failures,
        "pairwise_records": pairwise_records,
        "expected_pairwise_records": expected_pairwise,
        "pairwise_parse_failures": pairwise_parse_failures,
        "pairwise_inconsistent_records": inconsistent_records,
        "reference_records": reference_records,
        "expected_reference_records": expected_reference,
        "reference_parse_failures": reference_parse_failures,
        "expected_model_calls": expected_single * 2 + expected_pairwise * 2 + expected_reference,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-root",
        type=Path,
        default=ROOT / "runs" / "reproduction",
        help="directory containing {en,ko}/judgments",
    )
    parser.add_argument("--lang", choices=("en", "ko", "both"), default="both")
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    languages = ("en", "ko") if args.lang == "both" else (args.lang,)
    summaries = [verify_language(args.run_root.resolve(), lang) for lang in languages]
    payload = {
        "status": "complete",
        "judge_id": JUDGE_ID,
        "languages": summaries,
        "total_expected_model_calls": sum(
            summary["expected_model_calls"] for summary in summaries
        ),
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
