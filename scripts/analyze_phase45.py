#!/usr/bin/env python3
"""
Phase 4/5를 각각 독립적으로 읽을 수 있도록 요약 CSV와 figure를 만든다.

출력:
  - data/results_phase4_summary.csv
  - data/results_phase5_summary.csv
  - figures/fig17_phase4_internlm.png
  - figures/fig18_phase5_gpt4omini.png
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
FIG_DIR = ROOT / "figures"
FIG_DIR.mkdir(exist_ok=True)


def load_csv_rows(path: Path) -> List[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_scores(path: Path) -> Dict[str, float]:
    rows = load_csv_rows(path)
    return {row["model"]: float(row["overall"]) for row in rows}


def load_phase345_summary() -> Dict[str, dict]:
    rows = load_csv_rows(DATA_DIR / "results_phase345_judge_summary.csv")
    return {row["judge_label"]: row for row in rows}


def load_agreement() -> Dict[Tuple[str, str], dict]:
    rows = load_csv_rows(DATA_DIR / "results_phase345_judge_agreement.csv")
    out: Dict[Tuple[str, str], dict] = {}
    for row in rows:
        key = tuple(sorted((row["judge_a"], row["judge_b"])))
        out[key] = row
    return out


def metric_between(agreement: Dict[Tuple[str, str], dict], a: str, b: str) -> dict:
    return agreement[tuple(sorted((a, b)))]


def pct(x: str | float) -> float:
    return float(x) * 100.0


def r4(x: str | float) -> float:
    return round(float(x), 4)


def r2(x: str | float) -> float:
    return round(float(x), 2)


def save_csv(path: Path, rows: List[dict]) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_phase4_summary(
    summary: Dict[str, dict], agreement: Dict[Tuple[str, str], dict]
) -> List[dict]:
    rows = []
    for judge in ["InternLM2.5-7B", "InternLM2.5-20B"]:
        row = summary[judge]
        vs_qwen32 = metric_between(agreement, judge, "Qwen2.5-32B")
        vs_gpt = metric_between(agreement, judge, "GPT-4o-mini")
        rows.append(
            {
                "judge_label": judge,
                "top_model": row["top_model"],
                "score_range": r4(row["score_range"]),
                "error_rate_pct": r2(pct(row["error_rate"])),
                "inconsistency_rate_valid_pct": r2(pct(row["inconsistency_rate_valid"])),
                "decisive_rate_valid_pct": r2(pct(row["decisive_rate_valid"])),
                "first_pos_rate_pct": r2(pct(row["first_pos_rate"])),
                "spearman_vs_qwen32": r4(vs_qwen32["spearman_rho"]),
                "kendall_vs_qwen32": r4(vs_qwen32["kendall_tau_b"]),
                "exact_pairwise_vs_qwen32": r4(
                    vs_qwen32["exact_pairwise_agreement_valid"]
                ),
                "spearman_vs_gpt4omini": r4(vs_gpt["spearman_rho"]),
                "kendall_vs_gpt4omini": r4(vs_gpt["kendall_tau_b"]),
                "exact_pairwise_vs_gpt4omini": r4(
                    vs_gpt["exact_pairwise_agreement_valid"]
                ),
            }
        )
    return rows


def build_phase5_summary(
    summary: Dict[str, dict], agreement: Dict[Tuple[str, str], dict]
) -> List[dict]:
    row = summary["GPT-4o-mini"]
    vs_qwen32 = metric_between(agreement, "GPT-4o-mini", "Qwen2.5-32B")
    vs_internlm20 = metric_between(agreement, "GPT-4o-mini", "InternLM2.5-20B")
    return [
        {
            "judge_label": "GPT-4o-mini",
            "top_model": row["top_model"],
            "score_range": r4(row["score_range"]),
            "error_rate_pct": r2(pct(row["error_rate"])),
            "inconsistency_rate_valid_pct": r2(pct(row["inconsistency_rate_valid"])),
            "decisive_rate_valid_pct": r2(pct(row["decisive_rate_valid"])),
            "first_pos_rate_pct": r2(pct(row["first_pos_rate"])),
            "spearman_vs_qwen32": r4(vs_qwen32["spearman_rho"]),
            "kendall_vs_qwen32": r4(vs_qwen32["kendall_tau_b"]),
            "exact_pairwise_vs_qwen32": r4(
                vs_qwen32["exact_pairwise_agreement_valid"]
            ),
            "common_valid_pairwise_vs_qwen32": int(
                vs_qwen32["common_valid_pairwise_records"]
            ),
            "spearman_vs_internlm20b": r4(vs_internlm20["spearman_rho"]),
            "kendall_vs_internlm20b": r4(vs_internlm20["kendall_tau_b"]),
            "exact_pairwise_vs_internlm20b": r4(
                vs_internlm20["exact_pairwise_agreement_valid"]
            ),
            "common_valid_pairwise_vs_internlm20b": int(
                vs_internlm20["common_valid_pairwise_records"]
            ),
        }
    ]


def plot_phase4(
    scores_7b: Dict[str, float], scores_20b: Dict[str, float], summary: Dict[str, dict]
) -> None:
    models = sorted(scores_20b, key=lambda m: (-scores_20b[m], m))
    x = np.arange(len(models))
    width = 0.36

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.6), constrained_layout=True)

    ax = axes[0]
    ax.bar(x - width / 2, [scores_7b[m] for m in models], width=width, label="InternLM2.5-7B")
    ax.bar(
        x + width / 2,
        [scores_20b[m] for m in models],
        width=width,
        label="InternLM2.5-20B",
    )
    ax.set_title("Phase 4 overall scores by model")
    ax.set_ylabel("Overall score")
    ax.set_xticks(x)
    ax.set_xticklabels(models, rotation=25, ha="right")
    ax.legend(frameon=False, fontsize=9)
    ax.grid(axis="y", alpha=0.25)

    ax = axes[1]
    labels = ["InternLM2.5-7B", "InternLM2.5-20B"]
    decisive = [
        pct(summary["InternLM2.5-7B"]["decisive_rate_total"]),
        pct(summary["InternLM2.5-20B"]["decisive_rate_total"]),
    ]
    inconsistent = [
        pct(summary["InternLM2.5-7B"]["inconsistency_rate_total"]),
        pct(summary["InternLM2.5-20B"]["inconsistency_rate_total"]),
    ]
    error = [
        pct(summary["InternLM2.5-7B"]["error_rate"]),
        pct(summary["InternLM2.5-20B"]["error_rate"]),
    ]
    ax.bar(labels, decisive, label="Decisive", color="#4c78a8")
    ax.bar(labels, inconsistent, bottom=decisive, label="Inconsistent", color="#f58518")
    ax.bar(
        labels,
        error,
        bottom=np.array(decisive) + np.array(inconsistent),
        label="Error",
        color="#e45756",
    )
    ax.set_ylim(0, 100)
    ax.set_ylabel("Share of pairwise records (%)")
    ax.set_title("Phase 4 pairwise outcome composition")
    ax.legend(frameon=False, fontsize=9, loc="upper right")
    ax.grid(axis="y", alpha=0.25)
    ax.text(
        0.02,
        0.03,
        "7B keeps a plausible single-grade rank\nbut pairwise is dominated by errors (72.6%).\n20B is the usable Phase 4 judge.",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=9,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "alpha": 0.9},
    )

    fig.suptitle("Phase 4: InternLM2.5 cross-family judge check", fontsize=14)
    fig.savefig(FIG_DIR / "fig17_phase4_internlm.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_phase5(
    scores_qwen32: Dict[str, float], scores_gpt: Dict[str, float], summary: Dict[str, dict], agreement: Dict[Tuple[str, str], dict]
) -> None:
    models = sorted(scores_qwen32, key=lambda m: (-scores_qwen32[m], m))
    x = np.arange(len(models))
    width = 0.36

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.6), constrained_layout=True)

    ax = axes[0]
    ax.bar(x - width / 2, [scores_qwen32[m] for m in models], width=width, label="Qwen2.5-32B")
    ax.bar(x + width / 2, [scores_gpt[m] for m in models], width=width, label="GPT-4o-mini")
    ax.set_title("Phase 5 overall scores vs. Phase 3 main judge")
    ax.set_ylabel("Overall score")
    ax.set_xticks(x)
    ax.set_xticklabels(models, rotation=25, ha="right")
    ax.legend(frameon=False, fontsize=9)
    ax.grid(axis="y", alpha=0.25)

    ax = axes[1]
    pair = metric_between(agreement, "Qwen2.5-32B", "GPT-4o-mini")
    bars = {
        "Spearman": float(pair["spearman_rho"]),
        "Kendall": float(pair["kendall_tau_b"]),
        "Exact pairwise": float(pair["exact_pairwise_agreement_valid"]),
    }
    ax.bar(list(bars.keys()), list(bars.values()), color=["#4c78a8", "#72b7b2", "#f58518"])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Agreement")
    ax.set_title("Phase 5 agreement with Qwen2.5-32B")
    ax.grid(axis="y", alpha=0.25)
    for i, value in enumerate(bars.values()):
        ax.text(i, value + 0.03, f"{value:.3f}", ha="center", va="bottom", fontsize=10)
    ax.text(
        0.02,
        0.03,
        "GPT-4o-mini preserves the seen-7 rank pattern well\n"
        f"(n={pair['common_valid_pairwise_records']} common valid pairwise records),\n"
        "but remaining disagreements are still strongly order-sensitive.",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=9,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "alpha": 0.9},
    )

    fig.suptitle("Phase 5: GPT-4o-mini external judge check", fontsize=14)
    fig.savefig(FIG_DIR / "fig18_phase5_gpt4omini.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    summary = load_phase345_summary()
    agreement = load_agreement()

    scores_qwen32 = load_scores(DATA_DIR / "results_phase3_judge_32B.csv")
    scores_internlm7b = load_scores(DATA_DIR / "results_phase4_judge_internlm7b.csv")
    scores_internlm20b = load_scores(DATA_DIR / "results_phase4_judge_internlm20b.csv")
    scores_gpt = load_scores(DATA_DIR / "results_phase5_gpt4omini.csv")

    save_csv(DATA_DIR / "results_phase4_summary.csv", build_phase4_summary(summary, agreement))
    save_csv(DATA_DIR / "results_phase5_summary.csv", build_phase5_summary(summary, agreement))

    plot_phase4(scores_internlm7b, scores_internlm20b, summary)
    plot_phase5(scores_qwen32, scores_gpt, summary, agreement)

    print("Wrote:")
    print(" - data/results_phase4_summary.csv")
    print(" - data/results_phase5_summary.csv")
    print(" - figures/fig17_phase4_internlm.png")
    print(" - figures/fig18_phase5_gpt4omini.png")


if __name__ == "__main__":
    main()
