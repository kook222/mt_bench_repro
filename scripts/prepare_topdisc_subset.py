#!/usr/bin/env python3
"""
Prepare a reproducible TopDisc-N MT-Bench subset from dev-model single-grade scores.

출력:
  1) subset questions JSONL
  2) selected question_id / std metadata JSON

예시:
  export PYTHONPATH=src
  python3 scripts/prepare_topdisc_subset.py \
    --single-grade-dir data/judgments_phase3/judge_32B/single_grade \
    --top-n 40
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_DIR = _SCRIPT_DIR.parent
if str(_PROJECT_DIR / "src") not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR / "src"))

from mtbench_repro.io_utils import load_questions


DEFAULT_DEV_MODELS = [
    "Llama-3.1-8B-Instruct",
    "SOLAR-10.7B-Instruct",
    "gemma-2-9b-it",
    "Yi-1.5-9B-Chat",
    "Zephyr-7B-beta",
    "Mistral-7B-Instruct-v0.3",
    "Phi-3.5-mini-Instruct",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare TopDisc-N MT-Bench subset using dev-model single-grade scores."
    )
    parser.add_argument(
        "--single-grade-dir",
        type=Path,
        default=_PROJECT_DIR / "data" / "judgments_phase3" / "judge_32B" / "single_grade",
        help="single_grade 디렉토리 경로",
    )
    parser.add_argument(
        "--questions",
        type=Path,
        default=_PROJECT_DIR / "data" / "mt_bench_questions.jsonl",
        help="원본 MT-Bench questions JSONL 경로",
    )
    parser.add_argument(
        "--dev-models",
        nargs="+",
        default=DEFAULT_DEV_MODELS,
        help="TopDisc 계산에 사용할 dev 모델 목록",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=40,
        help="선택할 문항 수",
    )
    parser.add_argument(
        "--output-questions",
        type=Path,
        default=_PROJECT_DIR / "data" / "mt_bench_questions_topdisc40.jsonl",
        help="생성할 subset questions JSONL 경로",
    )
    parser.add_argument(
        "--output-metadata",
        type=Path,
        default=_PROJECT_DIR / "data" / "topdisc40_metadata.json",
        help="선택 문항 metadata JSON 경로",
    )
    return parser.parse_args()


def load_question_model_scores(single_grade_dir: Path, models: list[str]) -> dict[int, dict[str, float]]:
    scores_by_qid: dict[int, dict[str, list[float]]] = {}
    for model in models:
        path = single_grade_dir / f"{model}.jsonl"
        if not path.exists():
            raise FileNotFoundError(f"single_grade file not found: {path}")

        with path.open(encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                qid = int(row["question_id"])
                q_scores = scores_by_qid.setdefault(qid, {})
                per_model = q_scores.setdefault(model, [])
                score_turn1 = float(row.get("score_turn1", -1))
                score_turn2 = float(row.get("score_turn2", -1))
                if score_turn1 >= 0:
                    per_model.append(score_turn1)
                if score_turn2 >= 0:
                    per_model.append(score_turn2)

    complete: dict[int, dict[str, float]] = {}
    for qid, model_scores in scores_by_qid.items():
        if not all(model in model_scores and model_scores[model] for model in models):
            continue
        complete[qid] = {
            model: sum(model_scores[model]) / len(model_scores[model])
            for model in models
        }
    return complete


def compute_topdisc_scores(
    qid_model_scores: dict[int, dict[str, float]]
) -> list[dict[str, float | int]]:
    rows: list[dict[str, float | int]] = []
    for qid, scores in qid_model_scores.items():
        std = statistics.pstdev(scores.values())
        rows.append(
            {
                "question_id": qid,
                "std": std,
                "min_score": min(scores.values()),
                "max_score": max(scores.values()),
                "score_range": max(scores.values()) - min(scores.values()),
            }
        )
    rows.sort(key=lambda row: (-float(row["std"]), int(row["question_id"])))
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    args = parse_args()
    qid_model_scores = load_question_model_scores(args.single_grade_dir, args.dev_models)
    ranked = compute_topdisc_scores(qid_model_scores)

    if args.top_n > len(ranked):
        raise ValueError(
            f"Requested top-n={args.top_n}, but only {len(ranked)} complete questions available."
        )

    selected = ranked[: args.top_n]
    selected_qids = {int(row["question_id"]) for row in selected}

    questions = load_questions(args.questions)
    subset_rows = [q.to_dict() for q in questions if q.question_id in selected_qids]
    subset_rows.sort(key=lambda row: int(row["question_id"]))
    write_jsonl(args.output_questions, subset_rows)

    metadata = {
        "source_single_grade_dir": str(args.single_grade_dir),
        "source_questions": str(args.questions),
        "dev_models": args.dev_models,
        "top_n": args.top_n,
        "selected_question_ids_sorted_by_std": [int(row["question_id"]) for row in selected],
        "selected_questions_with_stats": selected,
    }
    args.output_metadata.parent.mkdir(parents=True, exist_ok=True)
    args.output_metadata.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[OK] wrote subset questions: {args.output_questions}")
    print(f"[OK] wrote metadata: {args.output_metadata}")
    print("Selected question_ids:")
    print(" ".join(str(qid) for qid in metadata["selected_question_ids_sorted_by_std"]))


if __name__ == "__main__":
    main()
