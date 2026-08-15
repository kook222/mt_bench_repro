#!/usr/bin/env python3
"""Import a verified Gemma 4 run into the publishable data tree."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.analysis.build_paper_artifacts import JUDGES, complete_judge_matrix  # noqa: E402
from scripts.tools.verify_gemma4_run import verify_language  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-root",
        type=Path,
        default=ROOT / "runs" / "reproduction",
        help="directory containing en/judgments and ko/judgments",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=ROOT / "data",
        help="publishable data directory",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_root = args.run_root.resolve()
    data_root = args.data_root.resolve()
    summaries = [verify_language(run_root, language) for language in ("en", "ko")]
    for summary in summaries:
        if summary["single_records"] != summary["expected_single_records"]:
            raise SystemExit(f"incomplete single grading: {summary}")
        if summary["pairwise_records"] != summary["expected_pairwise_records"]:
            raise SystemExit(f"incomplete pairwise grading: {summary}")
        if summary["reference_records"] != summary["expected_reference_records"]:
            raise SystemExit(f"incomplete reference grading: {summary}")

    targets = []
    for language in ("en", "ko"):
        source = run_root / language / "judgments" / "gemma4" / "judge_12B"
        target = data_root / language / "judgments" / "gemma4" / "judge_12B"
        if target.exists():
            raise SystemExit(
                f"target already exists: {target}. Remove it only after preserving the prior run."
            )
        targets.append((source, target))

    copied: list[Path] = []
    try:
        for source, target in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, target, ignore=shutil.ignore_patterns("*.lock"))
            copied.append(target)
        gemma = next(judge for judge in JUDGES if judge.optional)
        if not complete_judge_matrix(data_root, gemma):
            raise RuntimeError("imported Gemma 4 matrix is incomplete")
    except Exception:
        for target in copied:
            shutil.rmtree(target)
        raise

    print("[OK] imported verified Gemma 4 judgments for EN and KO")
    for _, target in targets:
        print(f"  {target}")


if __name__ == "__main__":
    main()
