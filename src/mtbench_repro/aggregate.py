# src/mtbench_repro/aggregate.py
"""
Judge 결과를 집계해 category별 점수, win rate, 모델 서열 trend를 출력.

왜 trend comparison 중심인가:
- 논문 재현 목표는 "GPT-4 점수 = 8.99 exact match"가 아니라
  "GPT-4 > GPT-3.5 > Vicuna-13B > LLaMA-13B 서열이 재현되는가"다.
- judge 모델 버전, 프롬프트 미세 차이, temperature 등으로 절대값은 달라질 수 있다.
- 따라서 이 파일은 순위 상관계수(Spearman), 카테고리별 갭, 서열 일치 여부를
  primary metric으로 사용하고 절대 점수는 참고값으로 출력한다.

출력 형식:
- 콘솔: 표 형태의 텍스트 (tabulate 없을 경우 plain text fallback)
- 선택적: CSV 파일 저장
"""

from __future__ import annotations
import argparse
import csv
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from mtbench_repro.io_utils import (
    list_available_models,
    load_pairwise_judgments,
    load_single_judgments,
)
from mtbench_repro.schemas import (
    JudgmentPairwise,
    JudgmentSingle,
    MT_BENCH_CATEGORIES,
)

logger = logging.getLogger(__name__)

# 논문 Table 7/8 기준 참조값 (재현 검증용 — exact match 목표 아님)
# 모델 서열 및 카테고리 패턴 확인에만 사용
PAPER_REFERENCE_SCORES: Dict[str, float] = {
    "gpt-4": 8.99,
    "gpt-3.5": 7.94,
    "vicuna-13b": 6.39,
    "alpaca-13b": 4.53,
    "llama-13b": 2.61,
}


# ===========================================================================
# Single-answer grading 집계
# ===========================================================================

def compute_single_scores(
    judgments_dir: str,
    model_ids: Optional[List[str]] = None,
) -> Dict[str, Dict[str, float]]:
    """
    Single-answer grading 결과에서 모델별·카테고리별 평균 점수 계산.

    반환 구조:
    {
        "vicuna-13b": {
            "writing": 7.2, "math": 4.1, ..., "overall": 6.0
        },
        ...
    }

    overall 계산 방식:
    - 논문 Table 8: 80문항 × 2-turn = 160턴의 평균 점수.
    - score_turn1 + score_turn2를 모두 포함해 평균.
    - 파싱 실패(-1.0) 항목은 제외 (NaN이 아닌 -1.0을 명시적으로 체크).

    Args:
        judgments_dir: data/judgments/ 디렉토리
        model_ids: 집계할 모델 목록. None이면 single_grade/ 디렉토리에서 자동 탐색.

    Returns:
        {model_id: {category: avg_score, "overall": avg_score}}
    """
    grade_dir = Path(judgments_dir) / "single_grade"

    if model_ids is None:
        model_ids = list_available_models(grade_dir)

    results: Dict[str, Dict[str, float]] = {}

    for model_id in model_ids:
        safe_id = model_id.replace("/", "_")
        path = grade_dir / f"{safe_id}.jsonl"
        if not path.exists():
            logger.warning(f"Single grade file not found: {path}")
            continue

        judgments = load_single_judgments(str(path))

        # 카테고리별 점수 누적
        cat_scores: Dict[str, List[float]] = defaultdict(list)
        all_scores: List[float] = []

        for j in judgments:
            for score in [j.score_turn1, j.score_turn2]:
                if score >= 0:  # 파싱 실패(-1.0) 제외
                    cat = j.category if j.category else "unknown"
                    cat_scores[cat].append(score)
                    all_scores.append(score)

        if not all_scores:
            logger.warning(f"No valid scores for model: {model_id}")
            continue

        model_result: Dict[str, float] = {}
        for cat in MT_BENCH_CATEGORIES:
            scores = cat_scores.get(cat, [])
            model_result[cat] = sum(scores) / len(scores) if scores else float("nan")

        model_result["overall"] = sum(all_scores) / len(all_scores)
        model_result["n_samples"] = float(len(all_scores))
        results[model_id] = model_result

    return results


# ===========================================================================
# Pairwise win rate 집계
# ===========================================================================

def compute_win_rates(
    judgments_dir: str,
    model_ids: Optional[List[str]] = None,
) -> Dict[str, Dict[str, float]]:
    """
    Pairwise 결과에서 모델별·카테고리별 win rate 계산.

    win rate 정의 (논문 Section 4.1):
    - 해당 모델이 winner인 판정 수 / 전체 (non-inconsistent, non-error) 판정 수
    - "tie"는 0.5승으로 계산 (논문 Fig 3 참조)
    - "inconsistent" / "error"는 집계에서 제외

    반환 구조:
    {
        "vicuna-13b": {
            "writing": 0.45, "math": 0.18, ...,
            "overall": 0.35, "n_games": 40.0
        }
    }

    Args:
        judgments_dir: data/judgments/ 디렉토리
        model_ids: 집계할 모델 목록. None이면 pairwise/ 디렉토리에서 자동 탐색.

    Returns:
        {model_id: {category: win_rate, "overall": win_rate}}
    """
    pairwise_dir = Path(judgments_dir) / "pairwise"
    if not pairwise_dir.exists():
        logger.warning(f"Pairwise directory not found: {pairwise_dir}")
        return {}

    # 모든 pairwise 파일 로드
    all_judgments: List[JudgmentPairwise] = []
    for path in sorted(pairwise_dir.glob("*.jsonl")):
        all_judgments.extend(load_pairwise_judgments(str(path)))

    if not all_judgments:
        return {}

    # 집계할 모델 목록 자동 추출
    if model_ids is None:
        model_ids_set: set = set()
        for j in all_judgments:
            model_ids_set.add(j.model_a)
            model_ids_set.add(j.model_b)
        model_ids = sorted(model_ids_set)

    # 모델별·카테고리별 (wins, total) 누적
    # wins는 0.5 단위를 허용하기 위해 float 사용
    wins: Dict[str, Dict[str, float]] = {m: defaultdict(float) for m in model_ids}
    totals: Dict[str, Dict[str, float]] = {m: defaultdict(float) for m in model_ids}

    for j in all_judgments:
        if j.winner in ("inconsistent", "error"):
            continue  # position bias로 판정 불일치한 항목은 집계 제외

        cat = j.category if j.category else "unknown"

        for model in [j.model_a, j.model_b]:
            if model not in model_ids:
                continue
            totals[model][cat] += 1.0
            totals[model]["overall"] += 1.0

            if j.winner == model:
                wins[model][cat] += 1.0
                wins[model]["overall"] += 1.0
            elif j.winner == "tie":
                wins[model][cat] += 0.5
                wins[model]["overall"] += 0.5

    # win rate 계산
    results: Dict[str, Dict[str, float]] = {}
    for model in model_ids:
        model_result: Dict[str, float] = {}
        for cat in MT_BENCH_CATEGORIES:
            t = totals[model].get(cat, 0.0)
            w = wins[model].get(cat, 0.0)
            model_result[cat] = w / t if t > 0 else float("nan")

        t_all = totals[model].get("overall", 0.0)
        w_all = wins[model].get("overall", 0.0)
        model_result["overall"] = w_all / t_all if t_all > 0 else float("nan")
        model_result["n_games"] = t_all
        results[model] = model_result

    return results


# ===========================================================================
# Trend comparison (핵심: 모델 서열이 논문과 일치하는가)
# ===========================================================================

def compute_rank_correlation(scores: Dict[str, float]) -> Optional[float]:
    """
    모델 점수를 논문 참조값(PAPER_REFERENCE_SCORES)과 비교해
    Spearman 순위 상관계수를 계산.

    왜 Spearman인가:
    - 절대값 차이(RMSE 등)는 judge 버전·프롬프트에 민감하다.
    - 순위 상관은 "GPT-4 > GPT-3.5 > Vicuna > LLaMA"라는 서열이
      유지되는지만 측정하므로 재현 목표에 더 적합하다.

    Args:
        scores: {model_id: score} dict (overall score 기준)

    Returns:
        Spearman rho (-1 ~ 1), 비교 가능한 모델이 2개 미만이면 None
    """
    # 공통 모델만 비교
    common = {
        m: s for m, s in scores.items()
        if m in PAPER_REFERENCE_SCORES and s == s  # NaN 제외
    }
    if len(common) < 2:
        logger.warning(
            "Spearman 계산을 위한 공통 모델이 2개 미만입니다. "
            "모델 ID가 PAPER_REFERENCE_SCORES 키와 일치하는지 확인하세요."
        )
        return None

    models = list(common.keys())
    our_scores = [common[m] for m in models]
    paper_scores = [PAPER_REFERENCE_SCORES[m] for m in models]

    # Spearman rho: 순위 기반 Pearson
    def rank_list(lst: List[float]) -> List[float]:
        sorted_idx = sorted(range(len(lst)), key=lambda i: lst[i])
        ranks = [0.0] * len(lst)
        for rank, idx in enumerate(sorted_idx):
            ranks[idx] = float(rank + 1)
        return ranks

    r_ours = rank_list(our_scores)
    r_paper = rank_list(paper_scores)
    n = len(r_ours)

    mean_o = sum(r_ours) / n
    mean_p = sum(r_paper) / n
    cov = sum((r_ours[i] - mean_o) * (r_paper[i] - mean_p) for i in range(n))
    std_o = (sum((r - mean_o) ** 2 for r in r_ours) ** 0.5)
    std_p = (sum((r - mean_p) ** 2 for r in r_paper) ** 0.5)

    if std_o == 0 or std_p == 0:
        return None

    return cov / (std_o * std_p)


def print_score_table(
    scores: Dict[str, Dict[str, float]],
    title: str = "MT-Bench Scores",
    sort_by: str = "overall",
) -> None:
    """
    카테고리별 점수 표를 콘솔에 출력.

    tabulate 패키지가 없어도 동작하도록 plain text fallback 구현.
    재현 시 어떤 환경에서도 결과를 확인할 수 있게 한다.

    Args:
        scores: compute_single_scores() 반환값
        title: 표 제목
        sort_by: 정렬 기준 컬럼 (기본: "overall")
    """
    if not scores:
        print(f"[{title}] No data available.")
        return

    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")

    # 모델을 sort_by 기준으로 내림차순 정렬
    sorted_models = sorted(
        scores.keys(),
        key=lambda m: scores[m].get(sort_by, float("-inf")),
        reverse=True,
    )

    # 헤더 — 컬럼 폭을 카테고리명 최대 길이 + 2로 계산
    # "extraction"(10자)처럼 정확히 10자인 이름이 있으면 열이 붙어 보이므로
    # max(len(cat)+2, 10)로 여유를 확보한다
    cat_w = max(len(c) for c in MT_BENCH_CATEGORIES) + 2  # 12
    col_w = max(len(m) for m in sorted_models + ["Model"]) + 2
    total_w = col_w + cat_w * len(MT_BENCH_CATEGORIES) + cat_w
    header = f"{'Model':<{col_w}}" + "".join(f"{c:>{cat_w}}" for c in MT_BENCH_CATEGORIES) + f"{'Overall':>{cat_w}}"
    print(header)
    print("-" * len(header))

    for model in sorted_models:
        row = f"{model:<{col_w}}"
        for cat in MT_BENCH_CATEGORIES:
            val = scores[model].get(cat, float("nan"))
            row += f"{val:>{cat_w}.2f}" if val == val else f"{'N/A':>{cat_w}}"
        overall = scores[model].get("overall", float("nan"))
        row += f"{overall:>{cat_w}.2f}" if overall == overall else f"{'N/A':>{cat_w}}"
        print(row)

    print(f"{'='*max(70, len(header))}\n")


def print_win_rate_table(
    win_rates: Dict[str, Dict[str, float]],
    title: str = "Win Rates",
) -> None:
    """
    카테고리별 win rate 표를 콘솔에 출력 (논문 Table 7 형식 참조).

    Args:
        win_rates: compute_win_rates() 반환값
        title: 표 제목
    """
    if not win_rates:
        print(f"[{title}] No data available.")
        return

    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")

    sorted_models = sorted(
        win_rates.keys(),
        key=lambda m: win_rates[m].get("overall", float("-inf")),
        reverse=True,
    )

    cat_w = max(len(c) for c in MT_BENCH_CATEGORIES) + 2  # 12
    col_w = max(len(m) for m in sorted_models + ["Model"]) + 2
    header = f"{'Model':<{col_w}}" + "".join(f"{c:>{cat_w}}" for c in MT_BENCH_CATEGORIES) + f"{'Overall':>{cat_w}}"
    print(header)
    print("-" * len(header))

    for model in sorted_models:
        row = f"{model:<{col_w}}"
        for cat in MT_BENCH_CATEGORIES:
            val = win_rates[model].get(cat, float("nan"))
            if val == val:
                row += f"{val*100:>{cat_w-1}.1f}%"
            else:
                row += f"{'N/A':>{cat_w}}"
        overall = win_rates[model].get("overall", float("nan"))
        row += f"{overall*100:>{cat_w-1}.1f}%" if overall == overall else f"{'N/A':>{cat_w}}"
        print(row)

    print(f"{'='*max(70, len(header))}\n")


def print_trend_summary(
    single_scores: Dict[str, Dict[str, float]],
    win_rates: Dict[str, Dict[str, float]],
) -> None:
    """
    논문 재현 관점에서 핵심 trend를 요약 출력.

    출력 내용:
    1. 모델 서열 (overall score 기준)
    2. 논문 참조값 대비 Spearman 순위 상관계수
    3. 카테고리별 서열 역전 여부 (논문 Table 7과 비교)
    4. math/reasoning/coding vs writing/roleplay 갭 비교
       (논문에서 GPT-4가 이 카테고리들에서 특히 강함)

    Args:
        single_scores: compute_single_scores() 반환값
        win_rates: compute_win_rates() 반환값
    """
    print(f"\n{'='*70}")
    print("  TREND SUMMARY (논문 재현 관점)")
    print(f"{'='*70}")

    # ── 1. 모델 서열 ──
    overall_scores = {
        m: v["overall"]
        for m, v in single_scores.items()
        if "overall" in v and v["overall"] == v["overall"]
    }

    if overall_scores:
        ranked = sorted(overall_scores.items(), key=lambda x: x[1], reverse=True)
        print("\n[1] 모델 서열 (overall score, 내림차순):")
        for rank, (model, score) in enumerate(ranked, start=1):
            paper_score = PAPER_REFERENCE_SCORES.get(model, None)
            paper_str = f"  (논문: {paper_score:.2f})" if paper_score else ""
            print(f"    {rank}. {model:<25} {score:.2f}{paper_str}")

        # ── 2. Spearman 상관 ──
        rho = compute_rank_correlation(overall_scores)
        print(f"\n[2] 논문 참조값과 Spearman 순위 상관계수: ", end="")
        if rho is not None:
            interpretation = (
                "매우 높음 ✓" if rho > 0.9 else
                "높음 ✓" if rho > 0.7 else
                "보통 △" if rho > 0.5 else
                "낮음 ✗"
            )
            print(f"{rho:.3f} ({interpretation})")
        else:
            print("계산 불가 (공통 모델명 확인 필요)")

    # ── 3. 카테고리별 서열 역전 감지 ──
    print("\n[3] 카테고리별 상위/하위 모델 서열 요약:")
    for cat in MT_BENCH_CATEGORIES:
        cat_scores = {
            m: v.get(cat, float("nan"))
            for m, v in single_scores.items()
        }
        valid = {m: s for m, s in cat_scores.items() if s == s}
        if not valid:
            continue
        best = max(valid, key=lambda m: valid[m])
        worst = min(valid, key=lambda m: valid[m])
        gap = valid[best] - valid[worst]
        print(f"    {cat:<12}: best={best} ({valid[best]:.2f})  "
              f"worst={worst} ({valid[worst]:.2f})  gap={gap:.2f}")

    # ── 4. 논문 핵심 패턴 검증 ──
    # 논문 Table 7: Vicuna-13B는 math/reasoning에서 특히 약함
    print("\n[4] 논문 핵심 패턴 검증:")
    for model, model_scores in single_scores.items():
        hard_cats = ["math", "reasoning", "coding"]
        easy_cats = ["writing", "roleplay", "humanities"]

        hard_avg = _safe_avg([model_scores.get(c, float("nan")) for c in hard_cats])
        easy_avg = _safe_avg([model_scores.get(c, float("nan")) for c in easy_cats])

        if hard_avg == hard_avg and easy_avg == easy_avg:
            diff = easy_avg - hard_avg
            flag = "↓ hard 약함 (논문과 일치 가능)" if diff > 1.0 else "≈ 균형"
            print(f"    {model:<25} hard_avg={hard_avg:.2f}  "
                  f"easy_avg={easy_avg:.2f}  diff={diff:+.2f}  {flag}")

    print(f"\n{'='*70}\n")


def _safe_avg(values: List[float]) -> float:
    """NaN을 제외한 평균. 유효값 없으면 NaN 반환."""
    valid = [v for v in values if v == v]
    return sum(valid) / len(valid) if valid else float("nan")


# ===========================================================================
# CSV 저장
# ===========================================================================

def save_scores_csv(
    scores: Dict[str, Dict[str, float]],
    output_path: str,
) -> None:
    """
    점수 집계 결과를 CSV로 저장. 노트북에서 pandas로 후처리할 때 유용.

    Args:
        scores: compute_single_scores() 또는 compute_win_rates() 반환값
        output_path: 저장할 CSV 파일 경로
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["model"] + MT_BENCH_CATEGORIES + ["overall", "n_samples"]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for model, model_scores in scores.items():
            row = {"model": model}
            row.update({k: f"{v:.4f}" if v == v else "NaN"
                        for k, v in model_scores.items()})
            writer.writerow(row)

    logger.info(f"Scores saved to CSV: {output_path}")


# ===========================================================================
# 통합 실행 함수
# ===========================================================================

def run_aggregate(
    judgments_dir: str,
    model_ids: Optional[List[str]] = None,
    output_csv: Optional[str] = None,
) -> Tuple[Dict[str, Dict[str, float]], Dict[str, Dict[str, float]]]:
    """
    모든 집계를 실행하고 결과를 출력하는 통합 함수.

    Args:
        judgments_dir: data/judgments/ 디렉토리
        model_ids: 집계할 모델 목록 (None이면 자동 탐색)
        output_csv: CSV 저장 경로 (None이면 저장 안 함)

    Returns:
        (single_scores, win_rates) tuple
    """
    logger.info("Aggregating single-answer scores...")
    single_scores = compute_single_scores(judgments_dir, model_ids)

    logger.info("Aggregating pairwise win rates...")
    win_rates = compute_win_rates(judgments_dir, model_ids)

    print_score_table(single_scores, title="MT-Bench Single-Answer Scores (GPT-4 Judge)")
    print_win_rate_table(win_rates, title="Pairwise Win Rates (논문 Figure 3 참조)")
    print_trend_summary(single_scores, win_rates)

    if output_csv:
        save_scores_csv(single_scores, output_csv)

    return single_scores, win_rates


# ===========================================================================
# CLI 엔트리포인트
# ===========================================================================

def parse_args() -> "argparse.Namespace":
    parser = argparse.ArgumentParser(description="MT-Bench 결과 집계 및 Trend 분석")
    parser.add_argument("--judgments-dir", type=str, default="data/judgments/",
                        help="판정 결과 디렉토리")
    parser.add_argument("--models", type=str, nargs="+", default=None,
                        help="집계할 모델 ID 목록 (기본: 자동 탐색)")
    parser.add_argument("--output-csv", type=str, default=None,
                        help="결과 CSV 저장 경로")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    run_aggregate(
        judgments_dir=args.judgments_dir,
        model_ids=args.models,
        output_csv=args.output_csv,
    )


if __name__ == "__main__":
    main()