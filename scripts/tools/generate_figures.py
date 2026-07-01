#!/usr/bin/env python3
"""
Generate README/paper figures from the committed aggregate CSV files.

The public repository does not include raw pairwise judgment JSONL files, so this
script only plots metrics that can be reproduced from committed CSVs.

Usage:
    python3 scripts/tools/generate_figures.py
"""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "figures" / "readme"
OUT.mkdir(parents=True, exist_ok=True)

CATEGORIES = [
    "writing",
    "roleplay",
    "extraction",
    "reasoning",
    "math",
    "coding",
    "stem",
    "humanities",
]

JUDGE_LABELS = OrderedDict(
    [
        ("qwen_7B", "Qwen-7B"),
        ("qwen_14B", "Qwen-14B"),
        ("qwen_32B", "Qwen-32B"),
        ("exaone_32B", "EXAONE-32B"),
        ("gpt4omini", "GPT-4o-mini"),
    ]
)

SCORE_FILES = {
    ("EN", "Qwen-7B"): ROOT / "data/en/results/results_phase3_judge_7B.csv",
    ("EN", "Qwen-14B"): ROOT / "data/en/results/results_phase3_judge_14B.csv",
    ("EN", "Qwen-32B"): ROOT / "data/en/results/results_phase3_judge_32B.csv",
    ("EN", "EXAONE-32B"): ROOT / "data/en/results/results_phase3_judge_exaone32B.csv",
    ("EN", "GPT-4o-mini"): ROOT / "data/en/results/results_en_judge_gpt4omini.csv",
    ("KO", "Qwen-7B"): ROOT / "data/ko/results/results_ko_judge_7B.csv",
    ("KO", "Qwen-14B"): ROOT / "data/ko/results/results_ko_judge_14B.csv",
    ("KO", "Qwen-32B"): ROOT / "data/ko/results/results_ko_judge_32B.csv",
    ("KO", "EXAONE-32B"): ROOT / "data/ko/results/results_ko_judge_exaone32B.csv",
    ("KO", "GPT-4o-mini"): ROOT / "data/ko/results/results_ko_judge_gpt4omini.csv",
}

REF_FILES = {
    ("EN", "Qwen-7B"): ROOT / "data/en/results/results_phase3_judge_7B_reference.csv",
    ("EN", "Qwen-14B"): ROOT / "data/en/results/results_phase3_judge_14B_reference.csv",
    ("EN", "Qwen-32B"): ROOT / "data/en/results/results_phase3_judge_32B_reference.csv",
    ("EN", "EXAONE-32B"): ROOT / "data/en/results/results_phase3_judge_exaone32B_reference.csv",
    ("EN", "GPT-4o-mini"): ROOT / "data/en/results/results_en_judge_gpt4omini_ref.csv",
    ("KO", "Qwen-7B"): ROOT / "data/ko/results/results_ko_judge_7B_reference.csv",
    ("KO", "Qwen-14B"): ROOT / "data/ko/results/results_ko_judge_14B_reference.csv",
    ("KO", "Qwen-32B"): ROOT / "data/ko/results/results_ko_judge_32B_reference.csv",
    ("KO", "EXAONE-32B"): ROOT / "data/ko/results/results_ko_judge_exaone32B_reference.csv",
    ("KO", "GPT-4o-mini"): ROOT / "data/ko/results/results_ko_judge_gpt4omini_ref.csv",
}

MODEL_LABELS = {
    "EXAONE-3.5-7.8B-Instruct": "EXAONE\n7.8B",
    "EEVE-Korean-Instruct-10.8B": "EEVE\n10.8B",
    "gemma-2-9b-it": "Gemma\n9B",
    "Llama-3.1-8B-Instruct": "Llama\n8B",
    "Mistral-7B-Instruct-v0.3": "Mistral\n7B",
    "Phi-3.5-mini-Instruct": "Phi\n3.5",
}

COLORS = {
    "en": "#4C78A8",
    "ko": "#F58518",
    "gap": "#E45756",
    "neutral": "#6C757D",
    "green": "#54A24B",
    "purple": "#B279A2",
}


def setup_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.28,
            "grid.linestyle": "--",
            "figure.dpi": 140,
            "savefig.dpi": 220,
            "savefig.bbox": "tight",
            "savefig.facecolor": "white",
            "axes.titleweight": "bold",
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
        }
    )


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def p_label(p_value: float) -> str:
    if p_value < 0.001:
        return "p<0.001"
    if p_value < 0.01:
        return "p<0.01"
    if p_value < 0.05:
        return "p<0.05"
    return f"p={p_value:.3f} ns"


def save(fig: plt.Figure, name: str) -> Path:
    path = OUT / name
    fig.savefig(path)
    plt.close(fig)
    print(f"saved {path.relative_to(ROOT)}")
    return path


def fig_en_ko_score_gap() -> None:
    en = read_csv(SCORE_FILES[("EN", "Qwen-32B")])
    ko = read_csv(SCORE_FILES[("KO", "Qwen-32B")])
    stat = read_csv(ROOT / "data/ko/results/results_stat_en_ko_diff.csv")
    stat = stat[stat["judge"] == "Qwen-32B"].set_index("model")

    df = en[["model", "overall", "n_samples"]].merge(
        ko[["model", "overall", "n_samples"]], on="model", suffixes=("_en", "_ko")
    )
    df["delta"] = df["overall_ko"] - df["overall_en"]
    df["p_value"] = df["model"].map(stat["p_value"])
    df = df.sort_values("delta")

    y = np.arange(len(df))
    fig, ax = plt.subplots(figsize=(9.4, 5.2))
    ax.scatter(df["overall_en"], y, s=95, color=COLORS["en"], label="EN", zorder=3)
    ax.scatter(df["overall_ko"], y, s=95, color=COLORS["ko"], label="KO", zorder=3)

    for idx, row in enumerate(df.itertuples(index=False)):
        ax.plot([row.overall_ko, row.overall_en], [idx, idx], color="#C9CED6", lw=4, zorder=1)
        ax.text(
            min(row.overall_en, row.overall_ko) - 0.05,
            idx,
            f"{row.delta:+.2f}",
            va="center",
            ha="right",
            fontsize=9,
            fontweight="bold",
            color=COLORS["gap"],
        )
        ax.text(
            max(row.overall_en, row.overall_ko) + 0.08,
            idx,
            p_label(row.p_value),
            va="center",
            ha="left",
            fontsize=8.5,
            color="#333333",
        )

    ax.set_yticks(y)
    ax.set_yticklabels([MODEL_LABELS[m] for m in df["model"]])
    ax.set_xlim(4.25, 8.9)
    ax.set_xlabel("MT-Bench score (1-10)")
    ax.set_title("Qwen-32B Judge: EN vs KO Score Gap")
    ax.legend(loc="lower right", frameon=False)
    ax.grid(True, axis="x")
    ax.grid(False, axis="y")
    ax.text(
        0.01,
        -0.16,
        "Left labels show KO-EN overall score delta; right labels show paired EN-KO permutation p-values.",
        transform=ax.transAxes,
        fontsize=8.5,
        color="#555555",
    )

    save(fig, "fig1_qwen32_en_ko_score_gap.png")


def fig_reliability_bias() -> None:
    comp = read_csv(ROOT / "data/ko/results/results_en_ko_comparison.csv")
    comp["judge_label"] = comp["judge"].map(JUDGE_LABELS)
    comp["en_fp_in_incon"] = comp["en_fp_pct"] / comp["en_incon_pct"] * 100
    comp["ko_fp_in_incon"] = comp["ko_fp_pct"] / comp["ko_incon_pct"] * 100

    x = np.arange(len(comp))
    width = 0.35
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10.5, 8.0), sharex=True)

    ax1.bar(x - width / 2, comp["en_incon_pct"], width, label="EN", color=COLORS["en"])
    ax1.bar(x + width / 2, comp["ko_incon_pct"], width, label="KO", color=COLORS["ko"])
    ax1.set_ylabel("Inconsistency (%)")
    ax1.set_ylim(0, 90)
    ax1.set_title("Pairwise Inconsistency: KO Is Lower Across Judges")
    ax1.legend(frameon=False, ncol=2, loc="upper right")
    for xpos, value in zip(x - width / 2, comp["en_incon_pct"]):
        ax1.text(xpos, value + 1.4, f"{value:.1f}", ha="center", fontsize=8.5)
    for xpos, value in zip(x + width / 2, comp["ko_incon_pct"]):
        ax1.text(xpos, value + 1.4, f"{value:.1f}", ha="center", fontsize=8.5)

    ax2.bar(
        x - width / 2,
        comp["en_fp_in_incon"],
        width,
        label="EN",
        color=COLORS["en"],
        alpha=0.9,
    )
    ax2.bar(
        x + width / 2,
        comp["ko_fp_in_incon"],
        width,
        label="KO",
        color=COLORS["ko"],
        alpha=0.9,
    )
    ax2.axhline(50, color="#555555", lw=1.2, ls=":", label="50%")
    ax2.set_ylabel("1st-position wins among inconsistent pairs (%)")
    ax2.set_ylim(0, 105)
    ax2.set_title("Residual Inconsistency Is Often Position-Sensitive")
    ax2.set_xticks(x)
    ax2.set_xticklabels(comp["judge_label"], rotation=0)
    for xpos, value in zip(x - width / 2, comp["en_fp_in_incon"]):
        ax2.text(xpos, value + 1.4, f"{value:.0f}", ha="center", fontsize=8.5)
    for xpos, value in zip(x + width / 2, comp["ko_fp_in_incon"]):
        ax2.text(xpos, value + 1.4, f"{value:.0f}", ha="center", fontsize=8.5)

    fig.suptitle("Judge Reliability and Position Bias", fontsize=14, fontweight="bold", y=0.99)
    fig.tight_layout()
    save(fig, "fig2_judge_reliability_position_bias.png")


def fig_rank_correlation() -> None:
    comp = read_csv(ROOT / "data/ko/results/results_en_ko_comparison.csv")
    comp["judge_label"] = comp["judge"].map(JUDGE_LABELS)
    x = np.arange(len(comp))
    width = 0.36

    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    ax.bar(
        x - width / 2,
        comp["spearman_rho_overall"],
        width,
        color=COLORS["purple"],
        label="All 80 questions",
    )
    ax.bar(
        x + width / 2,
        comp["spearman_rho_topdisc"],
        width,
        color=COLORS["green"],
        label="Top-discriminative subset",
    )
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Spearman rho (EN vs KO ranking)")
    ax.set_title("EN-KO Ranking Correlation Improves on Discriminative Questions")
    ax.set_xticks(x)
    ax.set_xticklabels(comp["judge_label"])
    ax.legend(frameon=False, loc="upper left")
    for xpos, value in zip(x - width / 2, comp["spearman_rho_overall"]):
        ax.text(xpos, value + 0.025, f"{value:.2f}", ha="center", fontsize=8.5)
    for xpos, value in zip(x + width / 2, comp["spearman_rho_topdisc"]):
        ax.text(xpos, value + 0.025, f"{value:.2f}", ha="center", fontsize=8.5)

    save(fig, "fig3_rank_correlation_topdisc.png")


def fig_ref_vs_nonref_qwen() -> None:
    df = read_csv(ROOT / "data/ko/results/results_stat_ref_vs_nonref.csv")
    judge_order = ["Qwen-7B", "Qwen-14B", "Qwen-32B"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), sharey=True)

    for ax, lang in zip(axes, ["EN", "KO"]):
        sub = df[df["lang"] == lang].set_index("judge").loc[judge_order].reset_index()
        x = np.arange(len(sub))
        width = 0.34
        ax.bar(x - width / 2, sub["nonref_mean"], width, color=COLORS["neutral"], label="Non-ref")
        ax.bar(x + width / 2, sub["ref_mean"], width, color=COLORS["gap"], label="Reference")
        for i, row in enumerate(sub.itertuples(index=False)):
            ax.text(
                i,
                max(row.nonref_mean, row.ref_mean) + 0.25,
                f"{row.diff_ref_minus_nonref:+.2f}\n{row.sig}",
                ha="center",
                va="bottom",
                fontsize=8.2,
                color="#333333",
            )
        ax.set_title(f"{lang}: Qwen Judges")
        ax.set_xticks(x)
        ax.set_xticklabels(sub["judge"])
        ax.set_ylim(0, 9.5)
        ax.grid(True, axis="y")
        ax.grid(False, axis="x")

    axes[0].set_ylabel("Mean turn-2 score")
    axes[1].legend(frameon=False, loc="upper right")
    fig.suptitle("Reference-Guided Scoring Lowers Scores on Hard Questions", fontsize=14, fontweight="bold")
    fig.tight_layout()
    save(fig, "fig4_ref_vs_nonref_qwen_stats.png")


def collect_parse_coverage() -> pd.DataFrame:
    rows = []
    for (lang, judge), path in SCORE_FILES.items():
        df = read_csv(path)
        for row in df.itertuples(index=False):
            expected = float(row.expected_count) * 2
            rows.append(
                {
                    "lang": lang,
                    "judge": judge,
                    "type": "single",
                    "model": row.model,
                    "valid": float(row.n_samples),
                    "expected": expected,
                    "failure_rate": 1.0 - float(row.n_samples) / expected,
                }
            )
    for (lang, judge), path in REF_FILES.items():
        df = read_csv(path)
        for row in df.itertuples(index=False):
            expected = float(row.expected_count)
            rows.append(
                {
                    "lang": lang,
                    "judge": judge,
                    "type": "reference",
                    "model": row.model,
                    "valid": float(row.n_samples),
                    "expected": expected,
                    "failure_rate": 1.0 - float(row.n_samples) / expected,
                }
            )
    return pd.DataFrame(rows)


def fig_parse_failure() -> None:
    df = collect_parse_coverage()
    summary = (
        df.groupby(["lang", "judge", "type"], as_index=False)
        .agg(valid=("valid", "sum"), expected=("expected", "sum"))
        .assign(failure_rate=lambda d: 1 - d["valid"] / d["expected"])
    )
    summary = summary.sort_values("failure_rate", ascending=False).head(12)
    summary["label"] = summary["lang"] + " " + summary["judge"] + "\n" + summary["type"]

    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    colors = [COLORS["gap"] if lang == "KO" else COLORS["en"] for lang in summary["lang"]]
    y = np.arange(len(summary))[::-1]
    ax.barh(y, summary["failure_rate"] * 100, color=colors)
    ax.set_yticks(y)
    ax.set_yticklabels(summary["label"])
    ax.set_xlabel("Parse failure rate (%)")
    ax.set_title("Highest Parse-Failure Settings in Public Aggregate CSVs")
    ax.set_xlim(0, max(35, float(summary["failure_rate"].max() * 115)))
    for ypos, row in zip(y, summary.itertuples(index=False)):
        failed = int(round(row.expected - row.valid))
        total = int(round(row.expected))
        ax.text(
            row.failure_rate * 100 + 0.6,
            ypos,
            f"{row.failure_rate*100:.1f}% ({failed}/{total})",
            va="center",
            fontsize=8.7,
        )
    ax.grid(True, axis="x")
    ax.grid(False, axis="y")

    save(fig, "fig5_parse_failure_public_csv.png")


def fig_key_numbers_table() -> None:
    q32 = read_csv(ROOT / "data/ko/results/results_stat_en_ko_diff.csv")
    q32 = q32[q32["judge"] == "Qwen-32B"].copy()
    rows = []
    for _, row in q32.sort_values("mean_diff", ascending=False).iterrows():
        rows.append(
            [
                f"Qwen-32B KO-EN score: {MODEL_LABELS.get(row['model'], row['model']).replace(chr(10), ' ')}",
                f"-{row['mean_diff']:.2f}",
                p_label(float(row["p_value"])),
            ]
        )

    incon = read_csv(ROOT / "data/ko/results/results_stat_inconsistency.csv")
    for _, row in incon[incon["comparison"] == "EN_vs_KO"].iterrows():
        rows.append(
            [
                f"{row['judge']} EN-KO inconsistency",
                f"-{abs(float(row['obs_diff']))*100:.1f} pp",
                p_label(float(row["p_value"])),
            ]
        )

    ref = read_csv(ROOT / "data/ko/results/results_stat_ref_vs_nonref.csv")
    ref = ref[(ref["judge"] == "Qwen-32B") & (ref["lang"].isin(["EN", "KO"]))]
    for _, row in ref.iterrows():
        rows.append(
            [
                f"{row['lang']} Qwen-32B ref minus non-ref",
                f"{row['diff_ref_minus_nonref']:.2f}",
                p_label(float(row["p_value"])),
            ]
        )

    fig, ax = plt.subplots(figsize=(9.5, 5.4))
    ax.axis("off")
    table = ax.table(
        cellText=rows,
        colLabels=["Metric", "Effect", "Permutation test"],
        colWidths=[0.55, 0.18, 0.22],
        cellLoc="left",
        colLoc="left",
        loc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9.0)
    table.scale(1, 1.45)
    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor("#E5E7EB")
        if r == 0:
            cell.set_facecolor("#111827")
            cell.set_text_props(color="white", weight="bold")
        elif r % 2 == 0:
            cell.set_facecolor("#F8FAFC")
        else:
            cell.set_facecolor("white")
    ax.set_title("Paper-Ready Statistical Checks from Committed CSVs", pad=20, fontweight="bold")

    save(fig, "fig6_key_statistics_table.png")


def print_audit() -> None:
    print("\ncoverage audit: rows with valid sample coverage < 99.5%")
    coverage = collect_parse_coverage()
    coverage["valid_rate"] = coverage["valid"] / coverage["expected"]
    bad = coverage[coverage["valid_rate"] < 0.995].sort_values("valid_rate")
    if bad.empty:
        print("  none")
        return
    for row in bad.itertuples(index=False):
        print(
            f"  {row.lang:2s} {row.judge:12s} {row.type:9s} "
            f"{row.model:35s} {int(row.valid):3d}/{int(row.expected):3d} "
            f"valid={row.valid_rate:.1%}"
        )


def main() -> None:
    setup_style()
    print(f"Generating figures under {OUT.relative_to(ROOT)}/")
    fig_en_ko_score_gap()
    fig_reliability_bias()
    fig_rank_correlation()
    fig_ref_vs_nonref_qwen()
    fig_parse_failure()
    fig_key_numbers_table()
    print_audit()


if __name__ == "__main__":
    main()
