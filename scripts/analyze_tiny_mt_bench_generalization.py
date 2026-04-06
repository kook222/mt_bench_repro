#!/usr/bin/env python3
"""
tinyMT-Bench generalization validation on unseen test models.

핵심 아이디어:
  - dev 모델 집합에서만 문항 변별도(std)를 계산해 TopDisc-N을 고른다.
  - test 모델 집합에서는 full-80 ranking과 subset ranking을 비교한다.
  - 같은 절차를 judge별 single_grade 디렉토리에 반복 적용한다.

출력:
  data/results_tiny_mt_bench_generalization_splits.csv
  data/results_tiny_mt_bench_generalization_summary.csv
  figures/fig15_tiny_mt_bench_generalization.png

예시:
  export PYTHONPATH=src
  python3 scripts/analyze_tiny_mt_bench_generalization.py \
    --judge qwen32=data/judgments_phase3/judge_32B/single_grade \
    --test-size 3 \
    --n-splits 20
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_DIR = _SCRIPT_DIR.parent
if str(_PROJECT_DIR / "src") not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR / "src"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

FIGURES_DIR = _PROJECT_DIR / "figures"
FIGURES_DIR.mkdir(exist_ok=True)
DATA_DIR = _PROJECT_DIR / "data"

DEFAULT_MODELS = [
    "Phi-3.5-mini-Instruct",
    "gemma-2-9b-it",
    "Yi-1.5-9B-Chat",
    "Mistral-7B-Instruct-v0.3",
    "SOLAR-10.7B-Instruct",
    "Zephyr-7B-beta",
    "Llama-3.1-8B-Instruct",
]
DEFAULT_N_SIZES = [10, 20, 25, 30, 40, 60, 80]

SUMMARY_CSV = DATA_DIR / "results_tiny_mt_bench_generalization_summary.csv"
SPLITS_CSV = DATA_DIR / "results_tiny_mt_bench_generalization_splits.csv"
FIG_PATH = FIGURES_DIR / "fig15_tiny_mt_bench_generalization.png"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="tinyMT-Bench generalization validation on unseen test models"
    )
    parser.add_argument(
        "--judge",
        action="append",
        default=[],
        help="label=single_grade_dir 형식. 여러 번 지정 가능.",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=DEFAULT_MODELS,
        help="분석할 모델 목록",
    )
    parser.add_argument(
        "--test-size",
        type=int,
        default=3,
        help="unseen test 모델 수 (권장: 3~5)",
    )
    parser.add_argument(
        "--dev-size",
        type=int,
        default=None,
        help="seen dev 모델 수 (미지정 시 전체-테스트)",
    )
    parser.add_argument(
        "--n-splits",
        type=int,
        default=20,
        help="무작위 split 반복 수. 가능한 조합 수보다 크면 exhaustive 사용",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="split/random sampling seed",
    )
    parser.add_argument(
        "--random-trials",
        type=int,
        default=200,
        help="split별 random subset 반복 횟수",
    )
    parser.add_argument(
        "--n-sizes",
        type=int,
        nargs="+",
        default=DEFAULT_N_SIZES,
        help="평가할 문항 수 N 목록",
    )
    parser.add_argument(
        "--dev-models",
        nargs="+",
        default=None,
        help="명시적 dev 모델 목록",
    )
    parser.add_argument(
        "--test-models",
        nargs="+",
        default=None,
        help="명시적 test 모델 목록",
    )
    return parser.parse_args()


def parse_judge_specs(values: list[str]) -> list[tuple[str, Path]]:
    if not values:
        default_dir = DATA_DIR / "judgments_phase3" / "judge_32B" / "single_grade"
        return [("qwen32", default_dir)]

    parsed: list[tuple[str, Path]] = []
    for value in values:
        if "=" not in value:
            raise ValueError(f"--judge 형식 오류: {value} (label=dir 필요)")
        label, raw_dir = value.split("=", 1)
        parsed.append((label.strip(), Path(raw_dir).expanduser()))
    return parsed


def load_per_question_scores(grade_dir: Path, models: list[str]) -> dict[int, dict[str, float]]:
    raw: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for model in models:
        path = grade_dir / f"{model}.jsonl"
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                qid = int(row["question_id"])
                if row.get("score_turn1", -1) >= 0:
                    raw[qid][model].append(float(row["score_turn1"]))
                if row.get("score_turn2", -1) >= 0:
                    raw[qid][model].append(float(row["score_turn2"]))

    complete: dict[int, dict[str, float]] = {}
    for qid, model_scores in raw.items():
        if not all(model in model_scores and model_scores[model] for model in models):
            continue
        complete[qid] = {
            model: sum(model_scores[model]) / len(model_scores[model]) for model in models
        }
    return complete


def rank_map(scores: dict[str, float]) -> dict[str, int]:
    ordered = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    return {model: idx + 1 for idx, (model, _) in enumerate(ordered)}


def spearman_rho(a: dict[str, float], b: dict[str, float]) -> float | None:
    common = sorted(set(a) & set(b))
    if len(common) < 2:
        return None
    ra = rank_map({m: a[m] for m in common})
    rb = rank_map({m: b[m] for m in common})
    n = len(common)
    d2 = sum((ra[m] - rb[m]) ** 2 for m in common)
    return 1 - 6 * d2 / (n * (n ** 2 - 1))


def kendall_tau(a: dict[str, float], b: dict[str, float]) -> float | None:
    common = sorted(set(a) & set(b))
    if len(common) < 2:
        return None
    concordant = 0
    discordant = 0
    for m1, m2 in itertools.combinations(common, 2):
        da = a[m1] - a[m2]
        db = b[m1] - b[m2]
        if da == 0 or db == 0:
            continue
        if da * db > 0:
            concordant += 1
        else:
            discordant += 1
    denom = concordant + discordant
    if denom == 0:
        return None
    return (concordant - discordant) / denom


def pairwise_agreement(a: dict[str, float], b: dict[str, float]) -> float | None:
    common = sorted(set(a) & set(b))
    if len(common) < 2:
        return None
    matches = 0.0
    total = 0
    for m1, m2 in itertools.combinations(common, 2):
        da = a[m1] - a[m2]
        db = b[m1] - b[m2]
        if da == 0 and db == 0:
            matches += 1.0
        elif da == 0 or db == 0:
            matches += 0.5
        elif da * db > 0:
            matches += 1.0
        total += 1
    if total == 0:
        return None
    return matches / total


def aggregate_model_scores(
    q_model_scores: dict[int, dict[str, float]],
    qids: list[int],
    models: list[str],
) -> dict[str, float]:
    acc: dict[str, list[float]] = defaultdict(list)
    for qid in qids:
        if qid not in q_model_scores:
            continue
        for model in models:
            score = q_model_scores[qid].get(model)
            if score is not None:
                acc[model].append(score)
    return {
        model: sum(values) / len(values)
        for model, values in acc.items()
        if values
    }


def compute_disc_order(
    q_model_scores: dict[int, dict[str, float]],
    dev_models: list[str],
) -> list[int]:
    scored: list[tuple[float, int]] = []
    for qid, scores in q_model_scores.items():
        values = [scores[m] for m in dev_models if m in scores]
        if len(values) != len(dev_models):
            continue
        std = statistics.pstdev(values)
        scored.append((std, qid))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [qid for _, qid in scored]


def evaluate_metrics(
    full_scores: dict[str, float],
    subset_scores: dict[str, float],
) -> dict[str, float]:
    rho = spearman_rho(full_scores, subset_scores)
    tau = kendall_tau(full_scores, subset_scores)
    pair_acc = pairwise_agreement(full_scores, subset_scores)
    top1_full = max(full_scores.items(), key=lambda x: (x[1], x[0]))[0]
    top1_subset = max(subset_scores.items(), key=lambda x: (x[1], x[0]))[0]
    return {
        "rho": float("nan") if rho is None else rho,
        "tau": float("nan") if tau is None else tau,
        "pairwise_acc": float("nan") if pair_acc is None else pair_acc,
        "top1_match": 1.0 if top1_full == top1_subset else 0.0,
    }


def build_splits(
    models: list[str],
    dev_models: list[str] | None,
    test_models: list[str] | None,
    dev_size: int | None,
    test_size: int,
    n_splits: int,
    seed: int,
) -> list[tuple[list[str], list[str]]]:
    if dev_models or test_models:
        if not dev_models or not test_models:
            raise ValueError("--dev-models와 --test-models는 함께 지정해야 합니다.")
        return [(sorted(dev_models), sorted(test_models))]

    if dev_size is None:
        dev_size = len(models) - test_size
    if dev_size <= 0 or test_size <= 0 or dev_size + test_size != len(models):
        raise ValueError("dev/test 크기 설정이 모델 수와 맞지 않습니다.")

    combos = list(itertools.combinations(sorted(models), dev_size))
    if n_splits >= len(combos):
        selected = combos
    else:
        rng = random.Random(seed)
        selected = rng.sample(combos, n_splits)

    splits: list[tuple[list[str], list[str]]] = []
    for combo in selected:
        dev = sorted(combo)
        test = sorted([m for m in models if m not in combo])
        splits.append((dev, test))
    return splits


def summarize_group(rows: list[dict], judge_label: str, n_questions: int) -> dict:
    def collect(key: str) -> list[float]:
        values = [float(r[key]) for r in rows if not math.isnan(float(r[key]))]
        return values

    topdisc_rhos = collect("topdisc_rho")
    random_mean_rhos = collect("random_mean_rho")
    topdisc_taus = collect("topdisc_tau")
    random_mean_taus = collect("random_mean_tau")
    topdisc_pairs = collect("topdisc_pairwise_acc")
    random_mean_pairs = collect("random_mean_pairwise_acc")
    topdisc_top1 = collect("topdisc_top1_match")
    random_mean_top1 = collect("random_mean_top1_match")

    return {
        "judge_label": judge_label,
        "n_questions": n_questions,
        "n_splits": len(rows),
        "dev_size": int(rows[0]["dev_size"]),
        "test_size": int(rows[0]["test_size"]),
        "topdisc_rho_mean": statistics.mean(topdisc_rhos),
        "topdisc_rho_min": min(topdisc_rhos),
        "topdisc_rho_max": max(topdisc_rhos),
        "random_mean_rho_mean": statistics.mean(random_mean_rhos),
        "random_mean_rho_min": min(random_mean_rhos),
        "random_mean_rho_max": max(random_mean_rhos),
        "topdisc_tau_mean": statistics.mean(topdisc_taus),
        "random_mean_tau_mean": statistics.mean(random_mean_taus),
        "topdisc_pairwise_acc_mean": statistics.mean(topdisc_pairs),
        "random_mean_pairwise_acc_mean": statistics.mean(random_mean_pairs),
        "topdisc_top1_match_rate": statistics.mean(topdisc_top1),
        "random_mean_top1_match_rate": statistics.mean(random_mean_top1),
        "topdisc_beats_random_rate": statistics.mean(
            [1.0 if float(r["topdisc_rho"]) > float(r["random_mean_rho"]) else 0.0 for r in rows]
        ),
    }


def save_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def make_figure(summary_rows: list[dict]) -> None:
    labels = sorted({row["judge_label"] for row in summary_rows})
    judge_colors = {
        label: color for label, color in zip(
            labels,
            ["#1565C0", "#E53935", "#2E7D32", "#8E24AA", "#EF6C00"],
        )
    }

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.2))
    panel_a, panel_b = axes

    for label in labels:
        rows = sorted(
            [row for row in summary_rows if row["judge_label"] == label],
            key=lambda x: int(x["n_questions"]),
        )
        ns = [int(r["n_questions"]) for r in rows]
        panel_a.plot(
            ns,
            [float(r["topdisc_rho_mean"]) for r in rows],
            marker="o",
            linewidth=2.2,
            color=judge_colors[label],
            label=f"{label}: TopDisc",
        )
        panel_a.plot(
            ns,
            [float(r["random_mean_rho_mean"]) for r in rows],
            marker="o",
            linestyle="--",
            linewidth=1.8,
            color=judge_colors[label],
            alpha=0.75,
            label=f"{label}: Random mean",
        )

        panel_b.plot(
            ns,
            [float(r["topdisc_top1_match_rate"]) for r in rows],
            marker="s",
            linewidth=2.2,
            color=judge_colors[label],
            label=f"{label}: TopDisc",
        )
        panel_b.plot(
            ns,
            [float(r["random_mean_top1_match_rate"]) for r in rows],
            marker="s",
            linestyle="--",
            linewidth=1.8,
            color=judge_colors[label],
            alpha=0.75,
            label=f"{label}: Random mean",
        )

    panel_a.axhline(0.95, color="gray", linestyle=":", linewidth=1.2, alpha=0.8)
    panel_a.set_title("(A) Unseen Test Ranking Retention", fontweight="bold")
    panel_a.set_xlabel("Number of Questions (N)")
    panel_a.set_ylabel("Spearman rho vs Full-80")
    panel_a.set_ylim(0.0, 1.05)
    panel_a.grid(True, linestyle="--", alpha=0.35)

    panel_b.set_title("(B) Top-1 Match Rate on Unseen Test Models", fontweight="bold")
    panel_b.set_xlabel("Number of Questions (N)")
    panel_b.set_ylabel("Top-1 Match Rate")
    panel_b.set_ylim(0.0, 1.05)
    panel_b.grid(True, linestyle="--", alpha=0.35)

    handles, labels_legend = panel_a.get_legend_handles_labels()
    fig.legend(handles, labels_legend, loc="lower center", ncol=2, frameon=False)
    fig.suptitle(
        "tinyMT-Bench Generalization Validation\n"
        "TopDisc-N selected on seen dev models, evaluated on unseen test models",
        fontsize=13,
        fontweight="bold",
    )
    plt.tight_layout(rect=[0, 0.1, 1, 0.92])
    plt.savefig(FIG_PATH, dpi=180, bbox_inches="tight")
    plt.close()


def main() -> None:
    args = parse_args()
    judge_specs = parse_judge_specs(args.judge)

    split_rows: list[dict] = []
    summary_rows: list[dict] = []

    for judge_label, grade_dir in judge_specs:
        if not grade_dir.exists():
            print(f"[skip] judge dir 없음: {grade_dir}")
            continue

        q_model_scores = load_per_question_scores(grade_dir, args.models)
        if not q_model_scores:
            print(f"[skip] 점수 로드 실패: {judge_label} ({grade_dir})")
            continue

        all_qids = sorted(q_model_scores.keys())
        splits = build_splits(
            models=args.models,
            dev_models=args.dev_models,
            test_models=args.test_models,
            dev_size=args.dev_size,
            test_size=args.test_size,
            n_splits=args.n_splits,
            seed=args.seed,
        )
        print(f"\n[{judge_label}] questions={len(all_qids)} splits={len(splits)}")

        rng = random.Random(args.seed)
        for split_idx, (dev_models, test_models) in enumerate(splits, start=1):
            disc_qids = compute_disc_order(q_model_scores, dev_models)
            full_test_scores = aggregate_model_scores(q_model_scores, all_qids, test_models)

            for n in sorted(args.n_sizes):
                n_eff = min(n, len(all_qids))
                top_qids = disc_qids[:n_eff]
                top_metrics = evaluate_metrics(
                    full_test_scores,
                    aggregate_model_scores(q_model_scores, top_qids, test_models),
                )

                random_metric_rows = []
                for _ in range(args.random_trials):
                    sampled_qids = rng.sample(all_qids, n_eff)
                    random_metric_rows.append(
                        evaluate_metrics(
                            full_test_scores,
                            aggregate_model_scores(q_model_scores, sampled_qids, test_models),
                        )
                    )

                split_rows.append({
                    "judge_label": judge_label,
                    "split_id": split_idx,
                    "dev_models": ",".join(dev_models),
                    "test_models": ",".join(test_models),
                    "dev_size": len(dev_models),
                    "test_size": len(test_models),
                    "n_questions": n_eff,
                    "topdisc_rho": statistics.mean([top_metrics["rho"]]),
                    "topdisc_tau": statistics.mean([top_metrics["tau"]]),
                    "topdisc_pairwise_acc": statistics.mean([top_metrics["pairwise_acc"]]),
                    "topdisc_top1_match": top_metrics["top1_match"],
                    "random_mean_rho": statistics.mean([m["rho"] for m in random_metric_rows]),
                    "random_min_rho": min(m["rho"] for m in random_metric_rows),
                    "random_max_rho": max(m["rho"] for m in random_metric_rows),
                    "random_mean_tau": statistics.mean([m["tau"] for m in random_metric_rows]),
                    "random_mean_pairwise_acc": statistics.mean([m["pairwise_acc"] for m in random_metric_rows]),
                    "random_mean_top1_match": statistics.mean([m["top1_match"] for m in random_metric_rows]),
                })

        judge_rows = [row for row in split_rows if row["judge_label"] == judge_label]
        for n in sorted({int(row["n_questions"]) for row in judge_rows}):
            group = [row for row in judge_rows if int(row["n_questions"]) == n]
            summary_rows.append(summarize_group(group, judge_label, n))

    save_csv(SPLITS_CSV, split_rows)
    save_csv(SUMMARY_CSV, summary_rows)
    if summary_rows:
        make_figure(summary_rows)

    print("\n[saved]")
    print(f"  - {SPLITS_CSV}")
    print(f"  - {SUMMARY_CSV}")
    if summary_rows:
        print(f"  - {FIG_PATH}")


if __name__ == "__main__":
    main()
