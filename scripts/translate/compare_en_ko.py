#!/usr/bin/env python3
"""
scripts/translate/compare_en_ko.py

영어-한국어 실험 결과 비교 분석.

교수님 피드백: 기존 영어 데이터에서 나온 scaling vs position bias 패턴이
한국어 번역본에서도 동일하게 재현되는지 확인.

비교 항목 3개:

  [비교 1] Judge Scaling Trade-off 재현
    - 영어: judge 크기(7B→14B→32B) vs 모델 랭킹 안정성
    - 한국어: 동일 judge로 채점한 결과와 비교
    - 지표: Kendall τ (영어 judge 랭킹 vs 한국어 judge 랭킹)

  [비교 2] Position Bias 패턴 재현
    - 영어: pairwise judge에서 A-우선 편향 측정
    - 한국어: 동일 측정 → 편향 크기 비교 (영어 vs 한국어)
    - 지표: Position bias score = P(A wins | A first) - P(A wins | B first)

  [비교 3] Top-Disc 랭킹 상관관계
    - 영어 실험에서 변별력 높은 Top-20 문항 선택
    - 한국어 번역 후 동일 문항 기준 랭킹 → Spearman ρ(영어, 한국어)
    - 높은 ρ(>0.8) → 번역이 변별력 구조를 보존했다는 증거

사용법:
    export PYTHONPATH=src
    python3 scripts/translate/compare_en_ko.py

    # 특정 judge만 비교
    python3 scripts/translate/compare_en_ko.py --judge gpt4omini

출력:
    data/ko/results/results_en_ko_comparison.csv
    figures/ko/fig_en_ko_scaling_comparison.png
    figures/ko/fig_en_ko_position_bias.png
    figures/ko/fig_en_ko_ranking_correlation.png

NOTE: 한국어 데이터(data/ko/results/) 생성 후 실행 가능.
      현재는 스켈레톤 — Phase 1 완료 후 구현 예정.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mtbench_repro.schemas import MT_BENCH_CATEGORIES

DATA_EN = PROJECT_ROOT / "data" / "en"
DATA_KO = PROJECT_ROOT / "data" / "ko"
FIGURES_KO = PROJECT_ROOT / "figures" / "ko"


def load_results(csv_path: Path) -> Dict[str, Dict[str, float]]:
    """results CSV → {model: {category: score}}"""
    scores: Dict[str, Dict[str, float]] = {}
    if not csv_path.exists():
        return scores
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            model = row["model"]
            scores[model] = {}
            for cat in MT_BENCH_CATEGORIES + ["overall"]:
                try:
                    scores[model][cat] = float(row[cat])
                except (KeyError, ValueError):
                    scores[model][cat] = float("nan")
    return scores


def rank_models(scores: Dict[str, Dict[str, float]], key: str = "overall") -> List[str]:
    """모델을 key 점수 기준 내림차순 정렬 → 순위 리스트 반환."""
    valid = {m: s[key] for m, s in scores.items() if not math.isnan(s.get(key, float("nan")))}
    return sorted(valid, key=lambda m: valid[m], reverse=True)


def spearman_rho(rank_a: List[str], rank_b: List[str]) -> float:
    """두 랭킹 리스트의 Spearman ρ. 공통 모델만 사용."""
    common = [m for m in rank_a if m in rank_b]
    if len(common) < 3:
        return float("nan")
    pos_a = {m: i for i, m in enumerate(rank_a)}
    pos_b = {m: i for i, m in enumerate(rank_b)}
    n = len(common)
    d2 = sum((pos_a[m] - pos_b[m]) ** 2 for m in common)
    return 1 - 6 * d2 / (n * (n * n - 1))


def compare_scaling(en_results: Dict[str, Path], ko_results: Dict[str, Path]) -> None:
    """[비교 1] Judge scaling 패턴 비교."""
    print("\n[비교 1] Judge Scaling Trade-off")
    print(f"{'Judge':<20} {'EN rank (overall)':<25} {'KO rank (overall)':<25} {'Spearman ρ':>10}")
    print("-" * 80)

    for judge_label in sorted(set(en_results) & set(ko_results)):
        en_scores = load_results(en_results[judge_label])
        ko_scores = load_results(ko_results[judge_label])
        if not en_scores or not ko_scores:
            print(f"  {judge_label}: 데이터 없음")
            continue
        en_rank = rank_models(en_scores)
        ko_rank = rank_models(ko_scores)
        rho = spearman_rho(en_rank, ko_rank)
        print(f"  {judge_label:<18} {' > '.join(en_rank[:3]):<25} {' > '.join(ko_rank[:3]):<25} {rho:>10.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="영어-한국어 실험 결과 비교")
    parser.add_argument(
        "--judge",
        default=None,
        help="비교할 judge (없으면 전체). 예: gpt4omini, qwen_7B",
    )
    args = parser.parse_args()

    FIGURES_KO.mkdir(parents=True, exist_ok=True)
    (DATA_KO / "results").mkdir(parents=True, exist_ok=True)

    # 영어 결과 파일 매핑
    en_results = {
        "gpt4omini": DATA_EN / "results" / "scores_gpt4omini.csv",
        "qwen_7B":   DATA_EN / "results" / "scores_qwen7b.csv",
        "qwen_14B":  DATA_EN / "results" / "scores_qwen14b.csv",
        "qwen_32B":  DATA_EN / "results" / "scores_qwen32b.csv",
    }

    # 한국어 결과 파일 매핑 (Phase 1 완료 후 생성)
    ko_results = {
        "gpt4omini": DATA_KO / "results" / "results_gpt4omini.csv",
        "qwen_7B":   DATA_KO / "results" / "results_judge_7B.csv",
        "qwen_14B":  DATA_KO / "results" / "results_judge_14B.csv",
        "qwen_32B":  DATA_KO / "results" / "results_judge_32B.csv",
    }

    if args.judge:
        en_results = {k: v for k, v in en_results.items() if k == args.judge}
        ko_results = {k: v for k, v in ko_results.items() if k == args.judge}

    # 한국어 데이터 존재 확인
    available_ko = {k for k, v in ko_results.items() if v.exists()}
    if not available_ko:
        print("[경고] 한국어 실험 결과 없음 (data/ko/results/ 비어있음)")
        print("  Phase 1 완료 후 실행하세요:")
        print("  1. 한국어 질문으로 eval 모델 답변 생성")
        print("  2. judge 채점")
        print("  3. aggregate → data/ko/results/results_*.csv")
        print()
        print("[현재 영어 결과 요약]")
        for judge_label, path in sorted(en_results.items()):
            scores = load_results(path)
            if scores:
                rank = rank_models(scores)
                print(f"  {judge_label}: {' > '.join(rank[:4])}")
        return

    compare_scaling(en_results, ko_results)
    print("\n다음: figures/ko/ 에 비교 그래프 생성 (matplotlib)")


if __name__ == "__main__":
    main()
