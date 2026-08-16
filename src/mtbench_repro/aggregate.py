"""Aggregate MT-Bench scores and pairwise win rates."""

from __future__ import annotations
import argparse
import csv
import logging
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from mtbench_repro.io_utils import (
    load_pairwise_judgments,
    load_questions,
    load_single_judgments,
)
from mtbench_repro.schemas import (
    JudgmentPairwise,
    JudgmentSingle,
    MTBenchQuestion,
    MT_BENCH_CATEGORIES,
    REFERENCE_GUIDED_CATEGORIES,
)

logger = logging.getLogger(__name__)


def _prefer_candidate(candidate_tstamp: Optional[float], current_tstamp: Optional[float]) -> bool:
    """Return True when a duplicate candidate should replace the current record."""
    if candidate_tstamp is None:
        return current_tstamp is None
    if current_tstamp is None:
        return True
    return candidate_tstamp >= current_tstamp

def deduplicate_single_judgments(
    judgments: List[JudgmentSingle],
) -> List[JudgmentSingle]:
    """Keep one latest record for each judge/model/question execution unit."""
    unique: Dict[Tuple[str, str, int], JudgmentSingle] = {}
    duplicate_count = 0
    for judgment in judgments:
        key = (judgment.judge_id, judgment.model_id, judgment.question_id)
        current = unique.get(key)
        if current is not None:
            duplicate_count += 1
        if current is None or _prefer_candidate(judgment.tstamp, current.tstamp):
            unique[key] = judgment

    if duplicate_count:
        logger.warning("Excluded %d duplicate single-grade records", duplicate_count)
    return sorted(
        unique.values(),
        key=lambda j: (j.model_id, j.judge_id, j.question_id),
    )

def deduplicate_pairwise_judgments(
    judgments: List[JudgmentPairwise],
) -> List[JudgmentPairwise]:
    """Keep one latest record per judge, unordered model pair, question, and turn."""
    unique: Dict[Tuple[str, str, str, int, int], JudgmentPairwise] = {}
    duplicate_count = 0
    for judgment in judgments:
        model_left, model_right = sorted((judgment.model_a, judgment.model_b))
        key = (
            judgment.judge_id,
            model_left,
            model_right,
            judgment.question_id,
            judgment.turn,
        )
        current = unique.get(key)
        if current is not None:
            duplicate_count += 1
        if current is None or _prefer_candidate(judgment.tstamp, current.tstamp):
            unique[key] = judgment

    if duplicate_count:
        logger.warning("Excluded %d duplicate pairwise records", duplicate_count)
    return sorted(
        unique.values(),
        key=lambda j: (
            j.judge_id,
            min(j.model_a, j.model_b),
            max(j.model_a, j.model_b),
            j.question_id,
            j.turn,
        ),
    )

def _load_single_judgments_by_model(
    grade_dir: Path,
) -> Dict[str, List[JudgmentSingle]]:
    """Load every JSONL once and group by record model_id, not by filename stem."""
    all_judgments: List[JudgmentSingle] = []
    for path in sorted(grade_dir.glob("*.jsonl")):
        all_judgments.extend(load_single_judgments(str(path)))

    judge_ids = {judgment.judge_id for judgment in all_judgments}
    if len(judge_ids) > 1:
        raise ValueError(
            "single-grade directory contains multiple judge_id values: "
            f"{sorted(judge_ids)}. Aggregate each judge directory separately."
        )

    grouped: Dict[str, List[JudgmentSingle]] = defaultdict(list)
    for judgment in deduplicate_single_judgments(all_judgments):
        grouped[judgment.model_id].append(judgment)
    return dict(grouped)

def compute_single_scores(
    judgments_dir: str,
    model_ids: Optional[List[str]] = None,
    expected_questions: Optional[int] = None,
    expected_question_ids: Optional[set[int]] = None,
    allow_partial: bool = False,
) -> Dict[str, Dict[str, float]]:
    """
    Single-answer grading 결과에서 모델별·카테고리별 평균 점수 계산.

    반환 구조:
    ``{model_id: {category: score, "overall": score}}``를 반환한다.

    overall 계산 방식:
    - 80문항 × 2-turn = 160턴의 평균 점수.
    - score_turn1 + score_turn2를 모두 포함해 평균.
    - 파싱 실패(-1.0) 항목은 제외 (NaN이 아닌 -1.0을 명시적으로 체크).

    Args:
        judgments_dir: data/judgments/ 디렉토리
        model_ids: 집계할 모델 목록. None이면 single_grade/ 디렉토리에서 자동 탐색.

    Returns:
        {model_id: {category: avg_score, "overall": avg_score}}
    """
    grade_dir = Path(judgments_dir) / "single_grade"
    judgments_by_model = _load_single_judgments_by_model(grade_dir)

    if model_ids is None:
        model_ids = sorted(judgments_by_model)

    results: Dict[str, Dict[str, float]] = {}

    for model_id in model_ids:
        judgments = judgments_by_model.get(model_id, [])
        if not judgments:
            if (
                (expected_questions is not None or expected_question_ids is not None)
                and not allow_partial
            ):
                raise ValueError(
                    f"No single-grade records found for required model: {model_id}"
                )
            logger.warning("No single-grade records found for model: %s", model_id)
            continue

        observed_question_ids = {j.question_id for j in judgments}
        question_count = len(observed_question_ids)
        observed_samples = len(judgments) * 2

        cat_scores: Dict[str, List[float]] = defaultdict(list)
        all_scores: List[float] = []

        for j in judgments:
            for score in [j.score_turn1, j.score_turn2]:
                if score >= 0:
                    cat = j.category if j.category else "unknown"
                    cat_scores[cat].append(score)
                    all_scores.append(score)

        if not all_scores:
            if not allow_partial:
                raise ValueError(f"No valid scores for model: {model_id}")
            logger.warning(f"No valid scores for model: {model_id}")
            continue

        expected_count = (
            len(expected_question_ids)
            if expected_question_ids is not None
            else expected_questions
        )
        if expected_question_ids is not None:
            missing_ids = expected_question_ids - observed_question_ids
            unexpected_ids = observed_question_ids - expected_question_ids
            coverage = (
                len(observed_question_ids & expected_question_ids) / expected_count
                if expected_count
                else float("nan")
            )
            if (missing_ids or unexpected_ids) and not allow_partial:
                raise ValueError(
                    f"Incomplete single grading result for {model_id}: "
                    f"missing={sorted(missing_ids)}, "
                    f"unexpected={sorted(unexpected_ids)}"
                )
        elif expected_count is not None and question_count != expected_count:
            coverage = question_count / expected_count if expected_count else float("nan")
            if not allow_partial:
                raise ValueError(
                    "Incomplete single grading result for "
                    f"{model_id}: {question_count}/{expected_count} "
                    f"questions ({coverage * 100.0:.1f}% coverage)"
                )
        else:
            coverage = (
                question_count / expected_count
                if expected_count
                else float("nan")
            )

        model_result: Dict[str, float] = {}
        for cat in MT_BENCH_CATEGORIES:
            scores = cat_scores.get(cat, [])
            model_result[cat] = sum(scores) / len(scores) if scores else float("nan")

        model_result["overall"] = sum(all_scores) / len(all_scores)
        model_result["n_questions"] = float(question_count)
        model_result["n_samples"] = float(len(all_scores))
        model_result["n_observed_samples"] = float(observed_samples)
        model_result["n_expected_samples"] = float(
            expected_count * 2 if expected_count is not None else observed_samples
        )
        model_result["n_parse_failures"] = float(observed_samples - len(all_scores))
        model_result["parse_failure_rate"] = (
            (observed_samples - len(all_scores)) / observed_samples
            if observed_samples
            else float("nan")
        )
        model_result["coverage"] = coverage
        model_result["expected_count"] = (
            float(expected_count)
            if expected_count is not None
            else float("nan")
        )
        results[model_id] = model_result

    return results

def compute_reference_scores(
    judgments_dir: str,
    model_ids: Optional[List[str]] = None,
    expected_questions: Optional[int] = None,
    expected_question_ids: Optional[set[int]] = None,
    allow_partial: bool = False,
) -> Dict[str, Dict[str, float]]:
    """
    Reference-guided single grading 결과를 별도 집계.

    reference-guided single-grade prompt 기반 점수는 math/reasoning/coding 3개 카테고리의 2nd turn에만 해당하므로,
    main MT-Bench 점수와 섞지 않고 별도 표/CSV로 보고한다.
    """
    grade_dir = Path(judgments_dir) / "single_grade_ref"
    if not grade_dir.exists():
        if (
            (expected_questions is not None or expected_question_ids is not None)
            and model_ids
            and not allow_partial
        ):
            raise ValueError(f"Reference-grade directory not found: {grade_dir}")
        return {}
    judgments_by_model = _load_single_judgments_by_model(grade_dir)

    if model_ids is None:
        model_ids = sorted(judgments_by_model)

    results: Dict[str, Dict[str, float]] = {}

    for model_id in model_ids:
        judgments = judgments_by_model.get(model_id, [])
        if not judgments:
            if (
                (expected_questions is not None or expected_question_ids is not None)
                and not allow_partial
            ):
                raise ValueError(
                    "No reference-guided records found for required model: "
                    f"{model_id}"
                )
            continue

        observed_question_ids = {j.question_id for j in judgments}
        question_count = len(observed_question_ids)
        observed_samples = len(judgments)

        cat_scores: Dict[str, List[float]] = defaultdict(list)
        all_scores: List[float] = []

        for j in judgments:
            if j.score_turn2 >= 0:
                cat = j.category if j.category else "unknown"
                cat_scores[cat].append(j.score_turn2)
                all_scores.append(j.score_turn2)

        if not all_scores:
            if not allow_partial:
                raise ValueError(
                    f"No valid reference-guided scores for model: {model_id}"
                )
            logger.warning(f"No valid reference-guided scores for model: {model_id}")
            continue

        expected_count = (
            len(expected_question_ids)
            if expected_question_ids is not None
            else expected_questions
        )
        if expected_question_ids is not None:
            missing_ids = expected_question_ids - observed_question_ids
            unexpected_ids = observed_question_ids - expected_question_ids
            coverage = (
                len(observed_question_ids & expected_question_ids) / expected_count
                if expected_count
                else float("nan")
            )
            if (missing_ids or unexpected_ids) and not allow_partial:
                raise ValueError(
                    f"Incomplete reference-guided result for {model_id}: "
                    f"missing={sorted(missing_ids)}, "
                    f"unexpected={sorted(unexpected_ids)}"
                )
        elif expected_count is not None and question_count != expected_count:
            coverage = question_count / expected_count if expected_count else float("nan")
            if not allow_partial:
                raise ValueError(
                    "Incomplete reference-guided result for "
                    f"{model_id}: {question_count}/{expected_count} "
                    f"questions ({coverage * 100.0:.1f}% coverage)"
                )
        else:
            coverage = (
                question_count / expected_count
                if expected_count
                else float("nan")
            )

        model_result = {cat: float("nan") for cat in MT_BENCH_CATEGORIES}
        for cat in REFERENCE_GUIDED_CATEGORIES:
            scores = cat_scores.get(cat, [])
            model_result[cat] = sum(scores) / len(scores) if scores else float("nan")

        model_result["overall"] = sum(all_scores) / len(all_scores)
        model_result["n_questions"] = float(question_count)
        model_result["n_samples"] = float(len(all_scores))
        model_result["n_observed_samples"] = float(observed_samples)
        model_result["n_expected_samples"] = float(
            expected_count if expected_count is not None else observed_samples
        )
        model_result["n_parse_failures"] = float(observed_samples - len(all_scores))
        model_result["parse_failure_rate"] = (
            (observed_samples - len(all_scores)) / observed_samples
            if observed_samples
            else float("nan")
        )
        model_result["coverage"] = coverage
        model_result["expected_count"] = (
            float(expected_count)
            if expected_count is not None
            else float("nan")
        )
        results[model_id] = model_result

    return results

def compute_win_rates(
    judgments_dir: str,
    model_ids: Optional[List[str]] = None,
    expected_question_ids: Optional[set[int]] = None,
    allow_partial: bool = False,
) -> Dict[str, Dict[str, float]]:
    """
    Pairwise 결과에서 모델별·카테고리별 win rate 계산.

    win rate 정의:
    - 주 지표 ``overall``은 conservative MT-Bench 방식으로 ``tie``와
      AB/BA ``inconsistent``를 모두 각 모델의 0.5승으로 계산한다.
    - ``overall_consistent_only``는 ``inconsistent``를 제외한 조건부
      민감도 지표이다.
    - 파싱/API ``error``는 두 지표 분모에서 모두 제외한다.

    반환 구조:
    ``{model_id: {category: win_rate, "overall": win_rate}}``를 반환한다.

    Args:
        judgments_dir: data/judgments/ 디렉토리
        model_ids: 집계할 모델 목록. None이면 pairwise/ 디렉토리에서 자동 탐색.

    Returns:
        {model_id: {category: win_rate, "overall": win_rate}}
    """
    pairwise_dir = Path(judgments_dir) / "pairwise"
    if not pairwise_dir.exists():
        if expected_question_ids and model_ids and len(model_ids) >= 2 and not allow_partial:
            raise ValueError(f"Pairwise directory not found: {pairwise_dir}")
        logger.warning(f"Pairwise directory not found: {pairwise_dir}")
        return {}

    all_judgments: List[JudgmentPairwise] = []
    for path in sorted(pairwise_dir.glob("*.jsonl")):
        all_judgments.extend(load_pairwise_judgments(str(path)))
    all_judgments = deduplicate_pairwise_judgments(all_judgments)

    if not all_judgments:
        if expected_question_ids and model_ids and len(model_ids) >= 2 and not allow_partial:
            raise ValueError("No pairwise judgments found for required model pairs")
        return {}
    judge_ids = {judgment.judge_id for judgment in all_judgments}
    if len(judge_ids) > 1:
        raise ValueError(
            "pairwise directory contains multiple judge_id values: "
            f"{sorted(judge_ids)}. Aggregate each judge directory separately."
        )

    if model_ids is None:
        model_ids_set: set = set()
        for j in all_judgments:
            model_ids_set.add(j.model_a)
            model_ids_set.add(j.model_b)
        model_ids = sorted(model_ids_set)

    selected_models = set(model_ids)
    all_judgments = [
        judgment
        for judgment in all_judgments
        if judgment.model_a in selected_models and judgment.model_b in selected_models
    ]

    expected_units: set[tuple[str, str, int, int]] = set()
    if expected_question_ids is not None:
        expected_units = {
            (model_a, model_b, question_id, 2)
            for model_a, model_b in combinations(sorted(selected_models), 2)
            for question_id in expected_question_ids
        }
        observed_units = {
            (
                min(judgment.model_a, judgment.model_b),
                max(judgment.model_a, judgment.model_b),
                judgment.question_id,
                judgment.turn,
            )
            for judgment in all_judgments
        }
        missing_units = expected_units - observed_units
        unexpected_units = observed_units - expected_units
        if missing_units or unexpected_units:
            message = (
                "Incomplete pairwise coverage: "
                f"missing={len(missing_units)}, unexpected={len(unexpected_units)}, "
                f"expected={len(expected_units)}, observed={len(observed_units)}"
            )
            if not allow_partial:
                raise ValueError(message)
            logger.warning(message)

    wins: Dict[str, Dict[str, float]] = {m: defaultdict(float) for m in model_ids}
    totals: Dict[str, Dict[str, float]] = {m: defaultdict(float) for m in model_ids}
    consistent_wins: Dict[str, Dict[str, float]] = {
        m: defaultdict(float) for m in model_ids
    }
    consistent_totals: Dict[str, Dict[str, float]] = {
        m: defaultdict(float) for m in model_ids
    }
    pair_counts: Dict[str, Dict[str, float]] = {
        m: defaultdict(float) for m in model_ids
    }

    for j in all_judgments:
        involved_models = [m for m in (j.model_a, j.model_b) if m in model_ids]
        for model in involved_models:
            pair_counts[model]["total"] += 1.0

        if j.winner == "inconsistent":
            for model in involved_models:
                pair_counts[model]["inconsistent"] += 1.0
                totals[model][j.category if j.category else "unknown"] += 1.0
                totals[model]["overall"] += 1.0
                wins[model][j.category if j.category else "unknown"] += 0.5
                wins[model]["overall"] += 0.5
            continue
        if j.winner == "error" or j.winner not in (j.model_a, j.model_b, "tie"):
            for model in involved_models:
                pair_counts[model]["error"] += 1.0
            continue

        cat = j.category if j.category else "unknown"

        for model in involved_models:
            totals[model][cat] += 1.0
            totals[model]["overall"] += 1.0
            consistent_totals[model][cat] += 1.0
            consistent_totals[model]["overall"] += 1.0

            if j.winner == model:
                wins[model][cat] += 1.0
                wins[model]["overall"] += 1.0
                consistent_wins[model][cat] += 1.0
                consistent_wins[model]["overall"] += 1.0
            elif j.winner == "tie":
                wins[model][cat] += 0.5
                wins[model]["overall"] += 0.5
                consistent_wins[model][cat] += 0.5
                consistent_wins[model]["overall"] += 0.5

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
        consistent_total = consistent_totals[model].get("overall", 0.0)
        consistent_win = consistent_wins[model].get("overall", 0.0)
        model_result["overall_consistent_only"] = (
            consistent_win / consistent_total
            if consistent_total > 0
            else float("nan")
        )
        model_result["n_consistent_games"] = consistent_total
        model_result["n_pairs_total"] = pair_counts[model].get("total", 0.0)
        model_result["n_expected_pairs"] = float(
            len(expected_question_ids) * max(len(selected_models) - 1, 0)
            if expected_question_ids is not None
            else pair_counts[model].get("total", 0.0)
        )
        model_result["n_inconsistent"] = pair_counts[model].get("inconsistent", 0.0)
        model_result["n_errors"] = pair_counts[model].get("error", 0.0)
        model_result["valid_fraction"] = (
            t_all / model_result["n_pairs_total"]
            if model_result["n_pairs_total"] > 0
            else float("nan")
        )
        model_result["consistent_fraction"] = (
            consistent_total / model_result["n_pairs_total"]
            if model_result["n_pairs_total"] > 0
            else float("nan")
        )
        results[model] = model_result

    return results

def print_score_table(
    scores: Dict[str, Dict[str, float]],
    title: str = "MT-Bench Scores",
    sort_by: str = "overall",
) -> None:
    """
    카테고리별 점수 표를 콘솔에 출력.

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

    sorted_models = sorted(
        scores.keys(),
        key=lambda m: scores[m].get(sort_by, float("-inf")),
        reverse=True,
    )

    cat_w = max(len(c) for c in MT_BENCH_CATEGORIES) + 2
    col_w = max(len(m) for m in sorted_models + ["Model"]) + 2
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
    카테고리별 win rate 표를 콘솔에 출력.

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

    cat_w = max(len(c) for c in MT_BENCH_CATEGORIES) + 2
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

def print_reference_table(
    reference_scores: Dict[str, Dict[str, float]],
    title: str = "Reference-Guided Scores",
) -> None:
    """
    Reference-guided single grading 결과를 별도 표로 출력.

    main score와 동일 척도로 섞지 않기 위해 대상 카테고리만 보여준다.
    """
    if not reference_scores:
        return

    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")

    cats = REFERENCE_GUIDED_CATEGORIES
    sorted_models = sorted(
        reference_scores.keys(),
        key=lambda m: reference_scores[m].get("overall", float("-inf")),
        reverse=True,
    )

    col_w = max(len(m) for m in sorted_models + ["Model"]) + 2
    cat_w = max(len(c) for c in cats + ["Overall"]) + 2
    header = (
        f"{'Model':<{col_w}}"
        + "".join(f"{c:>{cat_w}}" for c in cats)
        + f"{'Overall':>{cat_w}}"
    )
    print(header)
    print("-" * len(header))

    for model in sorted_models:
        row = f"{model:<{col_w}}"
        for cat in cats:
            val = reference_scores[model].get(cat, float("nan"))
            row += f"{val:>{cat_w}.2f}" if val == val else f"{'N/A':>{cat_w}}"
        overall = reference_scores[model].get("overall", float("nan"))
        row += f"{overall:>{cat_w}.2f}" if overall == overall else f"{'N/A':>{cat_w}}"
        print(row)

    print(f"{'='*max(70, len(header))}\n")

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
    fieldnames = [
        "model",
        *MT_BENCH_CATEGORIES,
        "overall",
        "n_questions",
        "n_samples",
        "n_observed_samples",
        "n_expected_samples",
        "n_parse_failures",
        "parse_failure_rate",
        "coverage",
        "expected_count",
        "n_games",
        "overall_consistent_only",
        "n_consistent_games",
        "n_pairs_total",
        "n_inconsistent",
        "n_errors",
        "valid_fraction",
        "consistent_fraction",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for model, model_scores in scores.items():
            row = {"model": model}
            row.update({k: f"{v:.4f}" if v == v else "NaN"
                        for k, v in model_scores.items()})
            writer.writerow(row)

    logger.info(f"Scores saved to CSV: {output_path}")

def _default_reference_csv_path(output_csv: str) -> str:
    """main 결과 CSV 경로에서 reference-guided 결과 CSV 경로를 유도."""
    output_path = Path(output_csv)
    return str(output_path.with_name(f"{output_path.stem}_reference{output_path.suffix}"))

def _resolve_expected_reference_ids(
    questions: List["MTBenchQuestion"],
    judgments_dir: str,
    model_ids: Optional[List[str]],
    selection: str,
    allow_partial: bool,
) -> set[int]:
    """Resolve the explicit historical (29) versus current usable-turn2 set.

    ``auto`` accepts only one of the two question-derived sets. This preserves
    strict coverage for the committed legacy artifact while allowing a fresh
    v3 run to omit records that have no usable second-turn reference.
    """
    declared = {
        question.question_id
        for question in questions
        if question.reference is not None
        and question.category in REFERENCE_GUIDED_CATEGORIES
    }
    usable_turn2 = {
        question.question_id
        for question in questions
        if question.has_reference_for_turn(1)
        and question.category in REFERENCE_GUIDED_CATEGORIES
    }
    if selection == "historical-declared":
        return declared
    if selection == "usable-turn2":
        return usable_turn2
    if selection != "auto":
        raise ValueError(f"Unknown reference selection: {selection}")

    grade_dir = Path(judgments_dir) / "single_grade_ref"
    if not grade_dir.exists():
        return usable_turn2
    observed_by_model = _load_single_judgments_by_model(grade_dir)
    selected_models = model_ids or sorted(observed_by_model)
    observed_sets = {
        frozenset(judgment.question_id for judgment in observed_by_model.get(model, []))
        for model in selected_models
        if observed_by_model.get(model)
    }
    if not observed_sets:
        return usable_turn2
    if len(observed_sets) != 1:
        raise ValueError(
            "Reference-grade models use different question sets; choose a single "
            "protocol version before aggregation."
        )
    observed = set(next(iter(observed_sets)))
    if observed == declared:
        logger.info("Detected historical declared-reference set (%d items).", len(declared))
        return declared
    if observed == usable_turn2:
        logger.info("Detected v3 usable-turn2 reference set (%d items).", len(usable_turn2))
        return usable_turn2
    if allow_partial and observed <= declared:

        historical_only = declared - usable_turn2
        return declared if observed & historical_only else usable_turn2
    raise ValueError(
        "Reference-grade question IDs match neither supported protocol set: "
        f"observed={sorted(observed)}, historical={sorted(declared)}, "
        f"usable_turn2={sorted(usable_turn2)}"
    )

def run_aggregate(
    judgments_dir: str,
    model_ids: Optional[List[str]] = None,
    output_csv: Optional[str] = None,
    questions_path: Optional[str] = None,
    include_partial: bool = False,
    output_ref_csv: Optional[str] = None,
    reference_selection: str = "auto",
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
    expected_questions: Optional[int] = None
    expected_question_ids: Optional[set[int]] = None
    expected_reference_question_ids: Optional[set[int]] = None
    if questions_path:
        questions = load_questions(questions_path)
        expected_questions = len(questions)
        expected_question_ids = {question.question_id for question in questions}
        expected_reference_question_ids = _resolve_expected_reference_ids(
            questions,
            judgments_dir,
            model_ids,
            reference_selection,
            include_partial,
        )

    logger.info("Aggregating single-answer scores...")
    single_scores = compute_single_scores(
        judgments_dir,
        model_ids,
        expected_questions=expected_questions,
        expected_question_ids=expected_question_ids,
        allow_partial=include_partial,
    )

    selected_models = model_ids or sorted(single_scores.keys())
    if model_ids and not include_partial:
        missing_single_models = sorted(set(model_ids) - set(single_scores))
        if missing_single_models:
            raise ValueError(
                "Incomplete single-grade coverage for models: "
                f"{missing_single_models}"
            )

    logger.info("Aggregating pairwise win rates...")
    win_rates = compute_win_rates(
        judgments_dir,
        selected_models,
        expected_question_ids=expected_question_ids,
        allow_partial=include_partial,
    )

    logger.info("Aggregating reference-guided scores...")
    reference_scores = compute_reference_scores(
        judgments_dir,
        selected_models,
        expected_question_ids=expected_reference_question_ids,
        allow_partial=include_partial,
    )
    if selected_models and not include_partial:
        missing_reference_models = sorted(
            set(selected_models) - set(reference_scores)
        )
        if missing_reference_models:
            raise ValueError(
                "Incomplete reference-guided coverage for models: "
                f"{missing_reference_models}"
            )

    judge_label = "Judge"
    print_score_table(single_scores, title=f"MT-Bench Single-Answer Scores ({judge_label})")
    print_win_rate_table(win_rates, title="Pairwise Win Rates (category별)")
    print_reference_table(reference_scores, title="Reference-Guided Scores (math/reasoning/coding)")

    if output_csv:
        save_scores_csv(single_scores, output_csv)
        if reference_scores:
            reference_csv = output_ref_csv or _default_reference_csv_path(output_csv)
            save_scores_csv(reference_scores, reference_csv)

    return single_scores, win_rates

def parse_args() -> "argparse.Namespace":
    parser = argparse.ArgumentParser(description="MT-Bench 결과 집계")
    parser.add_argument("--judgments-dir", type=str,
                        default="runs/reproduction/en/judgments/",
                        help="판정 결과 디렉토리")
    parser.add_argument("--questions-path", type=str,
                        default="data/en/questions.jsonl",
                        help="질문 JSONL 경로 (지정 시 complete coverage 검증 수행)")
    parser.add_argument("--models", type=str, nargs="+", default=None,
                        help="집계할 모델 ID 목록 (기본: 자동 탐색)")
    parser.add_argument("--output-csv", type=str, default=None,
                        help="결과 CSV 저장 경로")
    parser.add_argument("--output-ref-csv", type=str, default=None,
                        help="reference-guided 결과 CSV 저장 경로")
    parser.add_argument("--include-partial", action="store_true",
                        help="불완전한 partial 결과도 집계에 포함")
    parser.add_argument(
        "--reference-selection",
        choices=["auto", "historical-declared", "usable-turn2"],
        default="auto",
        help="과거 29문항과 v3 26문항 reference 집합 선택 (기본: 엄격 자동 식별)",
    )
    return parser.parse_args()

def main() -> None:
    args = parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if not args.models and not args.include_partial:
        raise ValueError(
            "Strict aggregation requires --models; use --include-partial "
            "only for an explicitly partial exploratory report."
        )

    run_aggregate(
        judgments_dir=args.judgments_dir,
        model_ids=args.models,
        output_csv=args.output_csv,
        questions_path=args.questions_path,
        include_partial=args.include_partial,
        output_ref_csv=args.output_ref_csv,
        reference_selection=args.reference_selection,
    )

if __name__ == "__main__":
    main()
