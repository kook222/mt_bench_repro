#!/usr/bin/env python3
"""
scripts/analysis/analyze_phase3.py

Phase 3 Judge Scaling Law 분석 스크립트.

두 가지 분석을 통합 실행:
1. Judge 크기 스케일링: judge 7B/14B/32B/72B 별 inconsistency율 + 모델 순위 비교
2. 문항 수 민감도: Phase 2 데이터에서 서브샘플링 → 몇 문항으로 순위가 수렴하는가

사용법:
    # 로컬 실행 (PYTHONPATH 필요)
    export PYTHONPATH=src
    python3 scripts/analysis/analyze_phase3.py

    # 옵션
    python3 scripts/analysis/analyze_phase3.py --project-dir /path/to/project
    python3 scripts/analysis/analyze_phase3.py --skip-scaling   # 스케일링 분석만 skip
    python3 scripts/analysis/analyze_phase3.py --skip-qsize     # 문항 수 분석만 skip
    python3 scripts/analysis/analyze_phase3.py --qsize-trials 20  # 서브샘플링 반복 횟수
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── 경로 설정 ─────────────────────────────────────────────────────────────────
# scripts/ 에서 실행되므로 src/ 를 sys.path에 추가
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_DIR = _SCRIPT_DIR.parents[1]
if str(_PROJECT_DIR / "src") not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR / "src"))

from mtbench_repro.io_utils import (
    list_available_models,
    load_pairwise_judgments,
    load_single_judgments,
)
from mtbench_repro.schemas import MT_BENCH_CATEGORIES


# ============================================================================
# 공통 유틸
# ============================================================================

def spearman_rho(scores_a: Dict[str, float], scores_b: Dict[str, float]) -> Optional[float]:
    """
    두 모델 점수 dict의 Spearman 순위 상관계수.
    공통 모델만 사용. 2개 미만이면 None.
    """
    common = sorted(set(scores_a) & set(scores_b))
    if len(common) < 2:
        return None

    def rank_list(vals: List[float]) -> List[float]:
        idx_sorted = sorted(range(len(vals)), key=lambda i: vals[i])
        ranks = [0.0] * len(vals)
        for rank, idx in enumerate(idx_sorted):
            ranks[idx] = float(rank + 1)
        return ranks

    a_vals = [scores_a[m] for m in common]
    b_vals = [scores_b[m] for m in common]
    ra = rank_list(a_vals)
    rb = rank_list(b_vals)
    n = len(ra)
    mean_a, mean_b = sum(ra) / n, sum(rb) / n
    cov = sum((ra[i] - mean_a) * (rb[i] - mean_b) for i in range(n))
    std_a = sum((r - mean_a) ** 2 for r in ra) ** 0.5
    std_b = sum((r - mean_b) ** 2 for r in rb) ** 0.5
    if std_a == 0 or std_b == 0:
        return None
    return cov / (std_a * std_b)


# ============================================================================
# 1. Judge 크기 스케일링 분석
# ============================================================================

JUDGE_LABELS = ["judge_7B", "judge_14B", "judge_32B", "judge_72B"]
JUDGE_PARAMS = {"judge_7B": 7, "judge_14B": 14, "judge_32B": 32, "judge_72B": 72}


def compute_inconsistency_rate(judgments_dir: Path) -> Tuple[int, int, float]:
    """
    pairwise/ 디렉토리에서 inconsistency율 계산.
    반환: (total, n_inconsistent, rate)
    """
    pairwise_dir = judgments_dir / "pairwise"
    if not pairwise_dir.exists():
        return 0, 0, float("nan")

    total = 0
    n_inconsistent = 0
    for path in sorted(pairwise_dir.glob("*.jsonl")):
        for j in load_pairwise_judgments(path):
            total += 1
            if j.winner == "inconsistent":
                n_inconsistent += 1

    rate = n_inconsistent / total if total > 0 else float("nan")
    return total, n_inconsistent, rate


def compute_overall_scores(judgments_dir: Path) -> Dict[str, float]:
    """
    single_grade/ 에서 모델별 overall score (160턴 평균) 계산.
    파싱 실패(-1.0) 제외.
    """
    grade_dir = judgments_dir / "single_grade"
    if not grade_dir.exists():
        return {}

    scores: Dict[str, float] = {}
    for path in sorted(grade_dir.glob("*.jsonl")):
        model_id = path.stem
        judgments = load_single_judgments(path)
        valid = []
        for j in judgments:
            if j.score_turn1 >= 0:
                valid.append(j.score_turn1)
            if j.score_turn2 >= 0:
                valid.append(j.score_turn2)
        if valid:
            scores[model_id] = sum(valid) / len(valid)

    return scores


def run_scaling_analysis(phase3_dir: Path, output_csv: Path) -> None:
    """
    judge 4종의 inconsistency율과 모델 순위를 비교 분석.
    """
    print("\n" + "=" * 65)
    print("  [1] JUDGE SCALING LAW — inconsistency율 & 모델 순위")
    print("=" * 65)

    # ── 각 judge별 데이터 수집 ─────────────────────────────────────────────
    scaling_rows = []
    all_scores: Dict[str, Dict[str, float]] = {}  # label → {model: score}

    for label in JUDGE_LABELS:
        jdir = phase3_dir / label
        if not jdir.exists():
            print(f"  [SKIP] {label} — 디렉토리 없음: {jdir}")
            continue

        total, n_inc, rate = compute_inconsistency_rate(jdir)
        scores = compute_overall_scores(jdir)

        if total == 0 or not scores:
            print(f"  [SKIP] {label} — 데이터 없음")
            continue

        all_scores[label] = scores
        params = JUDGE_PARAMS[label]
        scaling_rows.append({
            "judge_label": label,
            "params_B": params,
            "total_pairwise": total,
            "n_inconsistent": n_inc,
            "inconsistency_rate": rate,
        })

        # 모델 순위 출력
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        print(f"\n  {label} (inconsistency={rate*100:.1f}%, n={total})")
        print(f"  {'순위':<4} {'모델':<35} {'score':>6}")
        print(f"  {'-'*50}")
        for rank, (model, score) in enumerate(ranked, 1):
            print(f"  {rank:<4} {model:<35} {score:>6.2f}")

    if not scaling_rows:
        print("\n  [INFO] Phase 3 judge 실행 완료 후 다시 실행하세요.")
        return

    # ── inconsistency율 스케일링 커브 ─────────────────────────────────────
    print("\n" + "-" * 65)
    print("  INCONSISTENCY SCALING CURVE")
    print(f"  {'Judge':<15} {'Params(B)':>10} {'Total':>8} {'Incons.':>8} {'Rate':>8}")
    print(f"  {'-'*55}")
    for row in scaling_rows:
        print(f"  {row['judge_label']:<15} {row['params_B']:>10}B "
              f"{row['total_pairwise']:>8} {row['n_inconsistent']:>8} "
              f"{row['inconsistency_rate']*100:>7.1f}%")

    # ── cross-judge Spearman ρ (모델 순위 일관성) ──────────────────────────
    labels_available = list(all_scores.keys())
    if len(labels_available) >= 2:
        print("\n  CROSS-JUDGE SPEARMAN ρ (모델 순위 일관성)")
        print(f"  {'':15}", end="")
        for lb in labels_available:
            print(f"  {lb:>12}", end="")
        print()
        for la in labels_available:
            print(f"  {la:<15}", end="")
            for lb in labels_available:
                if la == lb:
                    print(f"  {'---':>12}", end="")
                else:
                    rho = spearman_rho(all_scores[la], all_scores[lb])
                    s = f"{rho:.3f}" if rho is not None else "N/A"
                    print(f"  {s:>12}", end="")
            print()

    # ── CSV 저장 ──────────────────────────────────────────────────────────
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        fields = ["judge_label", "params_B", "total_pairwise", "n_inconsistent", "inconsistency_rate"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in scaling_rows:
            writer.writerow({
                **row,
                "inconsistency_rate": f"{row['inconsistency_rate']:.6f}",
            })
    print(f"\n  [저장] {output_csv}")


# ============================================================================
# 2. 문항 수 민감도 분석
# ============================================================================

def load_per_question_scores(
    judgments_dir: Path,
    min_questions: int = 60,
) -> Dict[str, Dict[int, float]]:
    """
    single_grade/ 에서 모델별·문항별 평균 점수 로드.
    min_questions 미만인 모델(mock/샘플 데이터)은 자동 제외.
    반환: {model_id: {question_id: avg_score}}
    """
    grade_dir = judgments_dir / "single_grade"
    if not grade_dir.exists():
        return {}

    result: Dict[str, Dict[int, float]] = {}
    for path in sorted(grade_dir.glob("*.jsonl")):
        model_id = path.stem
        q_scores: Dict[int, List[float]] = defaultdict(list)
        for j in load_single_judgments(path):
            if j.score_turn1 >= 0:
                q_scores[j.question_id].append(j.score_turn1)
            if j.score_turn2 >= 0:
                q_scores[j.question_id].append(j.score_turn2)
        if len(q_scores) < min_questions:
            # mock/샘플 데이터(3문항 등)는 제외
            continue
        result[model_id] = {qid: sum(vs) / len(vs) for qid, vs in q_scores.items()}

    return result


def run_qsize_analysis(
    phase2_judgments_dir: Path,
    output_csv: Path,
    subsample_sizes: List[int],
    n_trials: int,
) -> None:
    """
    문항 수 민감도: N개 문항 서브샘플 → Spearman ρ vs 80문항 전체 순위.
    """
    print("\n" + "=" * 65)
    print("  [2] 문항 수 민감도 — 몇 문항으로 순위가 수렴하는가")
    print("=" * 65)

    # Phase 2 single_grade 데이터 로드
    per_q = load_per_question_scores(phase2_judgments_dir)
    if not per_q:
        print(f"  [SKIP] Phase 2 single_grade 데이터 없음: {phase2_judgments_dir}/single_grade/")
        return

    # 전체 문항 ID 수집 (모든 모델에 공통인 것만)
    all_qids_per_model = [set(qscores.keys()) for qscores in per_q.values()]
    common_qids = sorted(set.intersection(*all_qids_per_model))
    total_q = len(common_qids)

    if total_q == 0:
        print("  [SKIP] 공통 question_id 없음.")
        return

    print(f"  사용 모델: {sorted(per_q.keys())}")
    print(f"  공통 문항 수: {total_q}")

    # 전체 문항 기준 모델 순위 (baseline)
    full_scores: Dict[str, float] = {
        model: sum(q_scores.get(qid, 0) for qid in common_qids) / total_q
        for model, q_scores in per_q.items()
    }

    print(f"\n  기준 순위 ({total_q}문항 전체):")
    for rank, (m, s) in enumerate(sorted(full_scores.items(), key=lambda x: x[1], reverse=True), 1):
        print(f"    {rank}. {m:<35} {s:.3f}")

    # 서브샘플링 분석
    rng = random.Random(42)
    qsize_rows = []
    print(f"\n  {'N문항':>6} {'평균 ρ':>8} {'최소 ρ':>8} {'최대 ρ':>8}  ({n_trials} trials)")
    print(f"  {'-'*45}")

    for n in subsample_sizes:
        if n >= total_q:
            rho = 1.0
            qsize_rows.append({"n_questions": n, "mean_rho": 1.0, "min_rho": 1.0, "max_rho": 1.0})
            print(f"  {n:>6} {'1.000':>8} {'1.000':>8} {'1.000':>8}  (전체)")
            continue

        rhos = []
        for _ in range(n_trials):
            sampled_qids = rng.sample(common_qids, n)
            sub_scores = {
                model: sum(q_scores.get(qid, 0) for qid in sampled_qids) / n
                for model, q_scores in per_q.items()
            }
            rho = spearman_rho(sub_scores, full_scores)
            if rho is not None:
                rhos.append(rho)

        if rhos:
            mean_rho = sum(rhos) / len(rhos)
            min_rho = min(rhos)
            max_rho = max(rhos)
        else:
            mean_rho = min_rho = max_rho = float("nan")

        qsize_rows.append({
            "n_questions": n,
            "mean_rho": mean_rho,
            "min_rho": min_rho,
            "max_rho": max_rho,
        })
        print(f"  {n:>6} {mean_rho:>8.3f} {min_rho:>8.3f} {max_rho:>8.3f}")

    # CSV 저장
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["n_questions", "mean_rho", "min_rho", "max_rho"])
        writer.writeheader()
        for row in qsize_rows:
            writer.writerow({
                k: f"{v:.6f}" if isinstance(v, float) and v == v else v
                for k, v in row.items()
            })
    print(f"\n  [저장] {output_csv}")


# ============================================================================
# CLI
# ============================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase 3 분석: Judge 스케일링 + 문항 수 민감도"
    )
    parser.add_argument(
        "--project-dir", type=str, default=None,
        help="프로젝트 루트 경로 (기본: 스크립트 상위 디렉토리)"
    )
    parser.add_argument(
        "--skip-scaling", action="store_true",
        help="Judge 크기 스케일링 분석 건너뜀"
    )
    parser.add_argument(
        "--skip-qsize", action="store_true",
        help="문항 수 민감도 분석 건너뜀"
    )
    parser.add_argument(
        "--qsize-trials", type=int, default=30,
        help="서브샘플링 반복 횟수 (기본: 30)"
    )
    parser.add_argument(
        "--qsize-sizes", type=int, nargs="+",
        default=[10, 20, 40, 60, 80],
        help="서브샘플링 문항 수 목록 (기본: 10 20 40 60 80)"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    project_dir = Path(args.project_dir) if args.project_dir else _PROJECT_DIR

    phase3_dir = project_dir / "data" / "judgments_phase3"
    phase2_judgments_dir = project_dir / "data" / "judgments_phase2"
    scaling_csv = project_dir / "data" / "results_phase3_scaling.csv"
    qsize_csv = project_dir / "data" / "results_phase3_qsize.csv"

    print("=" * 65)
    print("  Phase 3 Analysis")
    print(f"  project_dir  : {project_dir}")
    print(f"  phase3_dir   : {phase3_dir}")
    print(f"  phase2_judge : {phase2_judgments_dir}")
    print("=" * 65)

    if not args.skip_scaling:
        run_scaling_analysis(phase3_dir, scaling_csv)

    if not args.skip_qsize:
        run_qsize_analysis(
            phase2_judgments_dir,
            qsize_csv,
            subsample_sizes=args.qsize_sizes,
            n_trials=args.qsize_trials,
        )

    print("\n" + "=" * 65)
    print("  완료.")
    print("  결과 CSV:")
    if not args.skip_scaling and scaling_csv.exists():
        print(f"    스케일링 : {scaling_csv}")
    if not args.skip_qsize and qsize_csv.exists():
        print(f"    문항 수  : {qsize_csv}")
    print("=" * 65)


if __name__ == "__main__":
    main()
