#!/usr/bin/env python3
"""
scripts/generate_figures.py

Professional figures for the MT-Bench reproduction project.
Generates publication-quality plots for the README.

Usage:
    export PYTHONPATH=src
    python3 scripts/generate_figures.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
import numpy as np

# ── 경로 설정 ─────────────────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_DIR = _SCRIPT_DIR.parent
FIGURES_DIR = _PROJECT_DIR / "figures"
FIGURES_DIR.mkdir(exist_ok=True)

# ── 스타일 ────────────────────────────────────────────────────────────────────
FONT_FAMILY = "DejaVu Sans"
plt.rcParams.update({
    "font.family": FONT_FAMILY,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.grid.axis": "x",
    "grid.alpha": 0.35,
    "grid.linestyle": "--",
    "figure.dpi": 150,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
    "savefig.facecolor": "white",
})

# ── 컬러 팔레트 ───────────────────────────────────────────────────────────────
PALETTE_MAIN = [
    "#2196F3",  # blue
    "#4CAF50",  # green
    "#FF9800",  # orange
    "#9C27B0",  # purple
    "#F44336",  # red
    "#00BCD4",  # cyan
    "#795548",  # brown
]
JUDGE_COLORS = {
    "7B":  "#64B5F6",
    "14B": "#42A5F5",
    "32B": "#1565C0",
}

CATEGORIES = ["writing", "roleplay", "extraction", "reasoning", "math", "coding", "stem", "humanities"]
CAT_LABELS  = ["Writing", "Roleplay", "Extraction", "Reasoning", "Math", "Coding", "STEM", "Humanities"]

# ── 데이터 ────────────────────────────────────────────────────────────────────

# Phase 1
PHASE1_DATA = {
    "model": "Qwen2.5-7B\n(self-judge)",
    "scores": [7.60, 7.95, 7.45, 7.20, 8.80, 8.80, 8.55, 8.60],
    "overall": 8.12,
}

# Phase 2 (Qwen2.5-14B judge)
PHASE2_MODELS = [
    "Phi-3.5-mini",
    "gemma-2-9b",
    "Yi-1.5-9B",
    "Mistral-7B",
    "SOLAR-10.7B",
    "Zephyr-7B",
]
PHASE2_SCORES = {
    # writing, roleplay, extraction, reasoning, math, coding, stem, humanities
    "Phi-3.5-mini":  [8.25, 7.70, 7.65, 7.75, 8.30, 8.15, 8.25, 8.65],
    "gemma-2-9b":    [8.15, 8.00, 7.50, 7.70, 8.05, 7.95, 8.40, 8.50],
    "Yi-1.5-9B":     [8.10, 8.05, 8.05, 7.45, 8.00, 7.20, 8.50, 8.40],
    "Mistral-7B":    [8.25, 7.80, 7.70, 6.70, 6.75, 6.05, 8.35, 8.30],
    "SOLAR-10.7B":   [7.85, 6.55, 7.26, 6.85, 7.25, 4.95, 7.65, 8.20],
    "Zephyr-7B":     [7.60, 7.20, 7.40, 6.15, 6.35, 5.65, 8.10, 7.90],
}
PHASE2_OVERALL = {
    "Phi-3.5-mini": 8.09, "gemma-2-9b": 8.03, "Yi-1.5-9B": 7.97,
    "Mistral-7B": 7.49, "SOLAR-10.7B": 7.07, "Zephyr-7B": 7.04,
}
PHASE2_PAIRWISE = {
    "gemma-2-9b": 79.4, "Phi-3.5-mini": 76.3, "Yi-1.5-9B": 66.1,
    "Mistral-7B": 43.4, "SOLAR-10.7B": 25.2, "Zephyr-7B": 15.2,
}

# Phase 3 (judge 7B / 14B / 32B)
PHASE3_MODELS_FULL = [
    "Phi-3.5-mini", "gemma-2-9b", "Llama-3.1-8B",
    "Yi-1.5-9B", "Mistral-7B", "SOLAR-10.7B", "Zephyr-7B",
]
PHASE3_SCORES = {
    "7B": {
        "Phi-3.5-mini":  [8.05, 7.60, 7.45, 7.80, 8.45, 8.60, 8.15, 8.25],
        "gemma-2-9b":    [7.35, 8.05, 7.15, 7.15, 7.85, 8.50, 8.40, 8.50],
        "Llama-3.1-8B":  [7.70, 7.70, 7.65, 7.50, 7.65, 8.35, 8.35, 8.25],
        "Yi-1.5-9B":     [7.80, 7.90, 7.20, 7.80, 8.25, 7.75, 8.55, 8.60],
        "Mistral-7B":    [7.55, 7.50, 7.25, 7.50, 6.40, 6.95, 8.20, 8.25],
        "SOLAR-10.7B":   [7.80, 7.05, 7.05, 6.75, 7.35, 6.40, 8.20, 8.15],
        "Zephyr-7B":     [7.35, 7.25, 6.90, 6.40, 6.50, 6.95, 8.40, 7.85],
    },
    "14B": {
        "Phi-3.5-mini":  [8.25, 7.70, 7.65, 7.75, 8.30, 8.15, 8.25, 8.65],
        "gemma-2-9b":    [8.15, 8.00, 7.50, 7.70, 8.05, 7.95, 8.40, 8.50],
        "Llama-3.1-8B":  [8.15, 7.65, 8.45, 7.35, 8.35, 8.30, 8.50, 8.60],
        "Yi-1.5-9B":     [8.10, 8.05, 8.05, 7.45, 8.00, 7.20, 8.50, 8.40],
        "Mistral-7B":    [8.25, 7.80, 7.70, 6.70, 6.75, 6.05, 8.35, 8.30],
        "SOLAR-10.7B":   [7.85, 6.55, 7.26, 6.85, 7.25, 4.95, 7.65, 8.20],
        "Zephyr-7B":     [7.60, 7.20, 7.40, 6.15, 6.35, 5.65, 8.10, 7.90],
    },
    "32B": {
        "Phi-3.5-mini":  [8.05, 7.80, 7.45, 7.55, 8.35, 8.15, 8.40, 8.75],
        "gemma-2-9b":    [8.05, 7.95, 7.75, 7.35, 8.10, 8.50, 8.50, 8.58],
        "Llama-3.1-8B":  [7.85, 7.65, 7.75, 6.65, 7.45, 7.60, 8.35, 8.40],
        "Yi-1.5-9B":     [7.70, 8.05, 7.35, 7.15, 7.70, 7.35, 8.65, 8.35],
        "Mistral-7B":    [7.95, 7.60, 6.85, 6.40, 4.85, 6.45, 8.40, 8.20],
        "SOLAR-10.7B":   [7.60, 6.85, 6.50, 7.05, 6.50, 5.45, 7.95, 8.25],
        "Zephyr-7B":     [7.55, 7.60, 5.65, 5.20, 5.25, 5.65, 8.15, 7.90],
    },
}
PHASE3_OVERALL = {
    "7B":  {"Phi-3.5-mini": 8.04, "gemma-2-9b": 7.87, "Llama-3.1-8B": 7.89,
             "Yi-1.5-9B": 7.98, "Mistral-7B": 7.45, "SOLAR-10.7B": 7.34, "Zephyr-7B": 7.20},
    "14B": {"Phi-3.5-mini": 8.09, "gemma-2-9b": 8.03, "Llama-3.1-8B": 8.17,
             "Yi-1.5-9B": 7.97, "Mistral-7B": 7.49, "SOLAR-10.7B": 7.07, "Zephyr-7B": 7.04},
    "32B": {"Phi-3.5-mini": 8.06, "gemma-2-9b": 8.09, "Llama-3.1-8B": 7.71,
             "Yi-1.5-9B": 7.79, "Mistral-7B": 7.09, "SOLAR-10.7B": 7.02, "Zephyr-7B": 6.62},
}

# Inconsistency scaling data
SCALING_DATA = [
    {"label": "7B",  "params": 7,  "rate": 0.7875},
    {"label": "14B", "params": 14, "rate": 0.4685},
    {"label": "32B", "params": 32, "rate": 0.3286},
]

# Q-size sensitivity
QSIZE_DATA = [
    {"n": 10,  "mean": 0.777, "lo": 0.321, "hi": 0.964},
    {"n": 20,  "mean": 0.839, "lo": 0.464, "hi": 1.000},
    {"n": 40,  "mean": 0.857, "lo": 0.607, "hi": 1.000},
    {"n": 60,  "mean": 0.952, "lo": 0.643, "hi": 1.000},
    {"n": 80,  "mean": 1.000, "lo": 1.000, "hi": 1.000},
]

# Cross-judge Spearman ρ
SPEARMAN_RHO = np.array([
    [1.000, 0.821, 0.786],
    [0.821, 1.000, 0.750],
    [0.786, 0.750, 1.000],
])
JUDGE_LABELS = ["7B", "14B", "32B"]


# ─────────────────────────────────────────────────────────────────────────────
# Figure 1: Phase 2 Category Heatmap
# ─────────────────────────────────────────────────────────────────────────────
def fig_category_heatmap():
    models = list(PHASE2_SCORES.keys())
    data = np.array([PHASE2_SCORES[m] for m in models])

    fig, ax = plt.subplots(figsize=(11, 4.5))
    fig.patch.set_facecolor("white")

    im = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=4.5, vmax=9.0)

    ax.set_xticks(range(len(CATEGORIES)))
    ax.set_xticklabels(CAT_LABELS, fontsize=11, fontweight="bold")
    ax.set_yticks(range(len(models)))

    model_labels = [f"{m}  ({PHASE2_OVERALL[m]:.2f})" for m in models]
    ax.set_yticklabels(model_labels, fontsize=10.5)

    # 셀 텍스트
    for i in range(len(models)):
        for j in range(len(CATEGORIES)):
            val = data[i, j]
            color = "black" if val > 6.5 else "white"
            ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                    fontsize=9.5, color=color, fontweight="bold")

    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("Score (1–10)", fontsize=10)
    cbar.ax.tick_params(labelsize=9)

    ax.set_title("Phase 2: Per-Category Scores — Qwen2.5-14B Judge",
                 fontsize=13, fontweight="bold", pad=12)
    ax.spines[:].set_visible(False)
    ax.grid(False)
    ax.tick_params(top=True, bottom=False, labeltop=True, labelbottom=False)
    ax.xaxis.set_label_position("top")

    plt.tight_layout()
    out = FIGURES_DIR / "fig1_category_heatmap.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 2: Phase 2 Overall Rankings (Single + Pairwise)
# ─────────────────────────────────────────────────────────────────────────────
def fig_overall_rankings():
    # Sort by single score
    models_sorted = sorted(PHASE2_OVERALL, key=lambda m: PHASE2_OVERALL[m])
    single_vals   = [PHASE2_OVERALL[m] for m in models_sorted]

    # Pairwise — same order
    pw_vals = [PHASE2_PAIRWISE[m] for m in models_sorted]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))
    fig.patch.set_facecolor("white")

    colors = [PALETTE_MAIN[i] for i in range(len(models_sorted))]

    # ── Single ────────────────────────────────────────────────────────────────
    bars = ax1.barh(range(len(models_sorted)), single_vals, color=colors,
                    edgecolor="white", height=0.65)
    ax1.set_yticks(range(len(models_sorted)))
    ax1.set_yticklabels(models_sorted, fontsize=11)
    ax1.set_xlabel("Average Score (1–10)", fontsize=11)
    ax1.set_title("Single-Answer Grading\n(Qwen2.5-14B Judge)", fontsize=12, fontweight="bold")
    ax1.set_xlim(6.5, 8.6)
    ax1.axvline(x=np.mean(single_vals), color="gray", linestyle="--",
                linewidth=1, alpha=0.7, label="avg")

    for i, (bar, val) in enumerate(zip(bars, single_vals)):
        ax1.text(val + 0.02, i, f"{val:.2f}", va="center", fontsize=10, fontweight="bold",
                 color="#333")

    ax1.grid(True, axis="x", linestyle="--", alpha=0.4)
    ax1.set_axisbelow(True)
    ax1.spines["left"].set_visible(False)
    ax1.tick_params(left=False)

    # ── Pairwise ──────────────────────────────────────────────────────────────
    pw_order  = sorted(PHASE2_PAIRWISE, key=lambda m: PHASE2_PAIRWISE[m])
    pw_sorted = [PHASE2_PAIRWISE[m] for m in pw_order]
    pw_colors = [PALETTE_MAIN[PHASE2_MODELS.index(m)] for m in pw_order]

    bars2 = ax2.barh(range(len(pw_order)), pw_sorted, color=pw_colors,
                     edgecolor="white", height=0.65)
    ax2.set_yticks(range(len(pw_order)))
    ax2.set_yticklabels(pw_order, fontsize=11)
    ax2.set_xlabel("Win Rate (%)", fontsize=11)
    ax2.set_title("Pairwise Win Rate\n(Qwen2.5-14B Judge, AB/BA swap)", fontsize=12, fontweight="bold")
    ax2.set_xlim(0, 95)
    ax2.axvline(x=50, color="gray", linestyle="--", linewidth=1, alpha=0.7, label="50%")

    for i, (bar, val) in enumerate(zip(bars2, pw_sorted)):
        ax2.text(val + 1, i, f"{val:.1f}%", va="center", fontsize=10, fontweight="bold",
                 color="#333")

    ax2.grid(True, axis="x", linestyle="--", alpha=0.4)
    ax2.set_axisbelow(True)
    ax2.spines["left"].set_visible(False)
    ax2.tick_params(left=False)

    fig.suptitle("Phase 2 Model Rankings — 6 Models", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    out = FIGURES_DIR / "fig2_overall_rankings.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 3: Hard vs. Easy Gap
# ─────────────────────────────────────────────────────────────────────────────
def fig_hard_easy_gap():
    HARD_CATS = ["reasoning", "math", "coding"]
    EASY_CATS = ["writing", "roleplay", "humanities"]

    hard_idx = [CATEGORIES.index(c) for c in HARD_CATS]
    easy_idx = [CATEGORIES.index(c) for c in EASY_CATS]

    models = list(PHASE2_OVERALL.keys())
    models_sorted = sorted(models, key=lambda m: PHASE2_OVERALL[m], reverse=True)

    hard_avgs = [np.mean([PHASE2_SCORES[m][i] for i in hard_idx]) for m in models_sorted]
    easy_avgs = [np.mean([PHASE2_SCORES[m][i] for i in easy_idx]) for m in models_sorted]
    gaps      = [e - h for h, e in zip(hard_avgs, easy_avgs)]

    x = np.arange(len(models_sorted))
    width = 0.33

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))
    fig.patch.set_facecolor("white")

    # ── Grouped bar ───────────────────────────────────────────────────────────
    b1 = ax1.bar(x - width/2, hard_avgs, width, label="Hard (math/reasoning/coding)",
                 color="#EF5350", alpha=0.88, edgecolor="white")
    b2 = ax1.bar(x + width/2, easy_avgs, width, label="Easy (writing/roleplay/humanities)",
                 color="#42A5F5", alpha=0.88, edgecolor="white")

    ax1.set_xticks(x)
    ax1.set_xticklabels(models_sorted, rotation=20, ha="right", fontsize=10)
    ax1.set_ylabel("Average Score", fontsize=11)
    ax1.set_ylim(5.5, 9.5)
    ax1.set_title("Hard vs. Easy Category Scores", fontsize=12, fontweight="bold")
    ax1.legend(fontsize=9.5, framealpha=0.85)
    ax1.grid(True, axis="y", linestyle="--", alpha=0.4)
    ax1.set_axisbelow(True)

    # ── Gap bar ───────────────────────────────────────────────────────────────
    bar_colors = [PALETTE_MAIN[i] for i in range(len(models_sorted))]
    bars = ax2.bar(x, gaps, color=bar_colors, edgecolor="white", alpha=0.9)
    ax2.set_xticks(x)
    ax2.set_xticklabels(models_sorted, rotation=20, ha="right", fontsize=10)
    ax2.set_ylabel("Easy − Hard Gap", fontsize=11)
    ax2.set_title("Easy−Hard Gap\n(Larger gap = weaker on hard tasks)", fontsize=12, fontweight="bold")
    ax2.axhline(0, color="black", linewidth=0.8)
    ax2.grid(True, axis="y", linestyle="--", alpha=0.4)
    ax2.set_axisbelow(True)

    for bar, val in zip(bars, gaps):
        ax2.text(bar.get_x() + bar.get_width()/2, val + 0.02, f"+{val:.2f}",
                 ha="center", va="bottom", fontsize=10, fontweight="bold", color="#333")

    fig.suptitle("Phase 2: Hard vs. Easy Category Analysis", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    out = FIGURES_DIR / "fig3_hard_easy_gap.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 4: Judge Scaling Law
# ─────────────────────────────────────────────────────────────────────────────
def fig_judge_scaling():
    params = [d["params"] for d in SCALING_DATA]
    rates  = [d["rate"] * 100 for d in SCALING_DATA]
    labels = [d["label"] for d in SCALING_DATA]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.patch.set_facecolor("white")

    # ── Inconsistency curve ───────────────────────────────────────────────────
    ax1.plot(params, rates, "o-", color="#1565C0", linewidth=2.5,
             markersize=9, markerfacecolor="white", markeredgewidth=2.5, zorder=5)

    ax1.fill_between(params, rates, alpha=0.10, color="#1565C0")
    ax1.axhline(50, color="gray", linestyle="--", linewidth=1.2, alpha=0.7,
                label="50% (random)")

    for p, r, lbl in zip(params, rates, labels):
        ax1.annotate(f"  {r:.1f}%",
                     xy=(p, r), xytext=(p + 0.8, r + 1.5),
                     fontsize=12, fontweight="bold", color="#1565C0")

    ax1.set_xticks(params)
    ax1.set_xticklabels([f"Qwen2.5\n{l}" for l in labels], fontsize=11)
    ax1.set_ylabel("Pairwise Inconsistency Rate (%)", fontsize=11)
    ax1.set_xlabel("Judge Model Size", fontsize=11)
    ax1.set_ylim(0, 100)
    ax1.set_xlim(-2, 38)
    ax1.set_title("Judge Scaling Law\n(Inconsistency Rate vs. Judge Size)",
                  fontsize=12, fontweight="bold")
    ax1.legend(fontsize=10, framealpha=0.8)
    ax1.grid(True, axis="y", linestyle="--", alpha=0.4)
    ax1.set_axisbelow(True)

    # Add annotation for 46pp drop
    ax1.annotate("", xy=(32, rates[2]), xytext=(7, rates[0]),
                 arrowprops=dict(arrowstyle="<->", color="#D32F2F", lw=1.8))
    ax1.text(19, (rates[0] + rates[2]) / 2 + 3,
             f"↓{rates[0]-rates[2]:.1f}pp", ha="center", fontsize=11,
             color="#D32F2F", fontweight="bold")

    # ── Score range (discriminability) ───────────────────────────────────────
    ranges = []
    for j in ["7B", "14B", "32B"]:
        vals = list(PHASE3_OVERALL[j].values())
        ranges.append(max(vals) - min(vals))

    judge_params = [7, 14, 32]
    bar_colors   = [JUDGE_COLORS[j] for j in ["7B", "14B", "32B"]]

    bars = ax2.bar(range(3), ranges, color=bar_colors, edgecolor="white",
                   alpha=0.92, width=0.5)
    ax2.set_xticks(range(3))
    ax2.set_xticklabels([f"Qwen2.5\n{l}" for l in labels], fontsize=11)
    ax2.set_ylabel("Score Range (Max − Min)", fontsize=11)
    ax2.set_title("Score Range (Discriminability)\nLarger judge → more discriminative",
                  fontsize=12, fontweight="bold")
    ax2.set_ylim(0, 2.0)
    ax2.grid(True, axis="y", linestyle="--", alpha=0.4)
    ax2.set_axisbelow(True)

    for bar, val in zip(bars, ranges):
        ax2.text(bar.get_x() + bar.get_width()/2, val + 0.04,
                 f"{val:.2f}p", ha="center", va="bottom",
                 fontsize=12, fontweight="bold", color="#1565C0")

    fig.suptitle("Phase 3: Judge Scaling Law", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    out = FIGURES_DIR / "fig4_judge_scaling.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 5: Phase 3 Overall Scores by Judge Size
# ─────────────────────────────────────────────────────────────────────────────
def fig_phase3_scores():
    judge_sizes = ["7B", "14B", "32B"]
    models = PHASE3_MODELS_FULL
    # sort by 14B score (canonical)
    models_sorted = sorted(models, key=lambda m: PHASE3_OVERALL["14B"][m], reverse=True)

    x = np.arange(len(models_sorted))
    width = 0.25
    offsets = [-width, 0, width]

    fig, ax = plt.subplots(figsize=(12, 5.5))
    fig.patch.set_facecolor("white")

    for i, (j, offset) in enumerate(zip(judge_sizes, offsets)):
        vals = [PHASE3_OVERALL[j][m] for m in models_sorted]
        bars = ax.bar(x + offset, vals, width, label=f"Judge {j}",
                      color=list(JUDGE_COLORS.values())[i],
                      edgecolor="white", alpha=0.9)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width()/2, val + 0.04,
                    f"{val:.2f}", ha="center", va="bottom", fontsize=8.5,
                    color="#333", rotation=90)

    ax.set_xticks(x)
    ax.set_xticklabels(models_sorted, fontsize=11)
    ax.set_ylabel("MT-Bench Score (1–10)", fontsize=11)
    ax.set_ylim(5.5, 9.3)
    ax.set_title("Phase 3: Overall Scores by Judge Size (7B / 14B / 32B)",
                 fontsize=13, fontweight="bold")
    ax.legend(fontsize=11, framealpha=0.85, loc="upper right")
    ax.grid(True, axis="y", linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)

    plt.tight_layout()
    out = FIGURES_DIR / "fig5_phase3_scores.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 6: Cross-Judge Spearman ρ Heatmap
# ─────────────────────────────────────────────────────────────────────────────
def fig_spearman_heatmap():
    fig, ax = plt.subplots(figsize=(5, 4.5))
    fig.patch.set_facecolor("white")

    mask = np.eye(3, dtype=bool)
    data_masked = np.where(mask, np.nan, SPEARMAN_RHO)

    cmap = plt.cm.Blues.copy()
    cmap.set_bad("white")

    im = ax.imshow(data_masked, cmap=cmap, vmin=0.5, vmax=1.0, aspect="auto")

    # Diagonal — gray
    for i in range(3):
        rect = plt.Rectangle((i - 0.5, i - 0.5), 1, 1, fill=True,
                              facecolor="#EEEEEE", edgecolor="white", zorder=2)
        ax.add_patch(rect)
        ax.text(i, i, "—", ha="center", va="center",
                fontsize=14, color="#999", zorder=3)

    # Off-diagonal values
    for i in range(3):
        for j in range(3):
            if i != j:
                val = SPEARMAN_RHO[i, j]
                ax.text(j, i, f"{val:.3f}", ha="center", va="center",
                        fontsize=13, fontweight="bold", color="white" if val > 0.85 else "#1A237E",
                        zorder=3)

    ax.set_xticks(range(3))
    ax.set_yticks(range(3))
    ax.set_xticklabels([f"Judge {l}" for l in JUDGE_LABELS], fontsize=11)
    ax.set_yticklabels([f"Judge {l}" for l in JUDGE_LABELS], fontsize=11)

    cbar = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.03)
    cbar.set_label("Spearman ρ", fontsize=10)

    ax.set_title("Cross-Judge Spearman ρ\n(Model Ranking Consistency)", fontsize=12, fontweight="bold")
    ax.spines[:].set_visible(False)
    ax.grid(False)

    plt.tight_layout()
    out = FIGURES_DIR / "fig6_spearman_heatmap.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 7: Q-size Sensitivity
# ─────────────────────────────────────────────────────────────────────────────
def fig_qsize_sensitivity():
    ns    = [d["n"]    for d in QSIZE_DATA]
    means = [d["mean"] for d in QSIZE_DATA]
    los   = [d["lo"]   for d in QSIZE_DATA]
    his   = [d["hi"]   for d in QSIZE_DATA]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    fig.patch.set_facecolor("white")

    ax.fill_between(ns, los, his, alpha=0.18, color="#1565C0", label="min–max range")
    ax.plot(ns, means, "o-", color="#1565C0", linewidth=2.5,
            markersize=8, markerfacecolor="white", markeredgewidth=2.5,
            label="Mean Spearman ρ", zorder=5)

    ax.axhline(0.95, color="#E53935", linestyle="--", linewidth=1.3, alpha=0.85,
               label="ρ = 0.95 (stable)")
    ax.axvline(60, color="#E53935", linestyle=":", linewidth=1.3, alpha=0.85)

    for n, m, lo, hi in zip(ns, means, los, his):
        ax.annotate(f"{m:.3f}",
                    xy=(n, m), xytext=(n + 1, m - 0.03),
                    fontsize=10, fontweight="bold", color="#1565C0")

    ax.set_xlabel("Number of Questions", fontsize=11)
    ax.set_ylabel("Spearman ρ vs. Full 80-Question Ranking", fontsize=11)
    ax.set_title("Question Count Sensitivity\n(How many questions needed for stable ranking?)",
                 fontsize=12, fontweight="bold")
    ax.set_xlim(5, 85)
    ax.set_ylim(0.0, 1.10)
    ax.set_xticks(ns)
    ax.legend(fontsize=10, framealpha=0.85)
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)

    plt.tight_layout()
    out = FIGURES_DIR / "fig7_qsize_sensitivity.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 8: Comprehensive Summary (banner figure for README top)
# ─────────────────────────────────────────────────────────────────────────────
def fig_summary_banner():
    fig = plt.figure(figsize=(18, 12))
    fig.patch.set_facecolor("white")

    gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.52, wspace=0.38)

    # ── (A) Phase 2 Overall ───────────────────────────────────────────────────
    ax_a = fig.add_subplot(gs[0, 0])
    models_sorted = sorted(PHASE2_OVERALL, key=lambda m: PHASE2_OVERALL[m])
    vals = [PHASE2_OVERALL[m] for m in models_sorted]
    colors = [PALETTE_MAIN[i] for i in range(len(models_sorted))]
    bars = ax_a.barh(range(len(models_sorted)), vals, color=colors, edgecolor="white", height=0.65)
    ax_a.set_yticks(range(len(models_sorted)))
    ax_a.set_yticklabels(models_sorted, fontsize=10)
    ax_a.set_xlim(6.5, 8.6)
    ax_a.set_xlabel("Score (1–10)", fontsize=10)
    ax_a.set_title("(A) Phase 2: Single-Answer Scores\n(Qwen2.5-14B Judge)", fontsize=11, fontweight="bold")
    for i, (bar, val) in enumerate(zip(bars, vals)):
        ax_a.text(val + 0.02, i, f"{val:.2f}", va="center", fontsize=9.5, color="#333", fontweight="bold")
    ax_a.grid(True, axis="x", linestyle="--", alpha=0.4)
    ax_a.set_axisbelow(True)
    ax_a.spines["left"].set_visible(False)
    ax_a.tick_params(left=False)

    # ── (B) Phase 2 Heatmap (6 models) ───────────────────────────────────────
    ax_b = fig.add_subplot(gs[0, 1:])
    models_b = list(PHASE2_SCORES.keys())
    data_b   = np.array([PHASE2_SCORES[m] for m in models_b])
    im_b = ax_b.imshow(data_b, aspect="auto", cmap="RdYlGn", vmin=4.5, vmax=9.0)
    ax_b.set_xticks(range(len(CATEGORIES)))
    ax_b.set_xticklabels(CAT_LABELS, fontsize=10, fontweight="bold")
    ax_b.set_yticks(range(len(models_b)))
    ax_b.set_yticklabels([f"{m}  ({PHASE2_OVERALL[m]:.2f})" for m in models_b], fontsize=9.5)
    for i in range(len(models_b)):
        for j in range(len(CATEGORIES)):
            val = data_b[i, j]
            ax_b.text(j, i, f"{val:.1f}", ha="center", va="center",
                      fontsize=9, color="black" if val > 6.5 else "white", fontweight="bold")
    cbar_b = fig.colorbar(im_b, ax=ax_b, fraction=0.02, pad=0.01)
    cbar_b.ax.tick_params(labelsize=8)
    ax_b.set_title("(B) Phase 2: Per-Category Heatmap", fontsize=11, fontweight="bold")
    ax_b.spines[:].set_visible(False)
    ax_b.grid(False)
    ax_b.tick_params(top=True, bottom=False, labeltop=True, labelbottom=False)

    # ── (C) Judge Scaling ─────────────────────────────────────────────────────
    ax_c = fig.add_subplot(gs[1, 0])
    params = [d["params"] for d in SCALING_DATA]
    rates  = [d["rate"] * 100 for d in SCALING_DATA]
    ax_c.plot(params, rates, "o-", color="#1565C0", linewidth=2.5,
              markersize=9, markerfacecolor="white", markeredgewidth=2.5, zorder=5)
    ax_c.fill_between(params, rates, alpha=0.12, color="#1565C0")
    ax_c.axhline(50, color="gray", linestyle="--", linewidth=1, alpha=0.7)
    for p, r, lbl in zip(params, rates, [d["label"] for d in SCALING_DATA]):
        ax_c.annotate(f"  {r:.1f}%", xy=(p, r), xytext=(p + 0.5, r + 2.5),
                      fontsize=10, fontweight="bold", color="#1565C0")
    ax_c.set_xticks(params)
    ax_c.set_xticklabels([f"Qwen2.5\n{d['label']}" for d in SCALING_DATA], fontsize=10)
    ax_c.set_ylim(0, 100)
    ax_c.set_xlim(-3, 40)
    ax_c.set_ylabel("Inconsistency Rate (%)", fontsize=10)
    ax_c.set_title("(C) Judge Scaling Law\n(Inconsistency Rate)", fontsize=11, fontweight="bold")
    ax_c.grid(True, axis="y", linestyle="--", alpha=0.4)
    ax_c.set_axisbelow(True)

    # ── (D) Phase 3 Scores by Judge ───────────────────────────────────────────
    ax_d = fig.add_subplot(gs[1, 1])
    judge_sizes_d = ["7B", "14B", "32B"]
    models_d = sorted(PHASE3_MODELS_FULL, key=lambda m: PHASE3_OVERALL["14B"][m], reverse=True)
    x_d = np.arange(len(models_d))
    w_d = 0.25
    for i, (j, offset) in enumerate(zip(judge_sizes_d, [-w_d, 0, w_d])):
        vals_d = [PHASE3_OVERALL[j][m] for m in models_d]
        ax_d.bar(x_d + offset, vals_d, w_d,
                 label=f"Judge {j}", color=list(JUDGE_COLORS.values())[i],
                 edgecolor="white", alpha=0.9)
    ax_d.set_xticks(x_d)
    ax_d.set_xticklabels(models_d, rotation=30, ha="right", fontsize=9)
    ax_d.set_ylim(5.5, 9.2)
    ax_d.set_ylabel("MT-Bench Score", fontsize=10)
    ax_d.set_title("(D) Phase 3: Scores by Judge Size", fontsize=11, fontweight="bold")
    ax_d.legend(fontsize=9, framealpha=0.85)
    ax_d.grid(True, axis="y", linestyle="--", alpha=0.4)
    ax_d.set_axisbelow(True)

    # ── (E) Q-size ────────────────────────────────────────────────────────────
    ax_e = fig.add_subplot(gs[1, 2])
    ns_e    = [d["n"]    for d in QSIZE_DATA]
    means_e = [d["mean"] for d in QSIZE_DATA]
    los_e   = [d["lo"]   for d in QSIZE_DATA]
    his_e   = [d["hi"]   for d in QSIZE_DATA]
    ax_e.fill_between(ns_e, los_e, his_e, alpha=0.18, color="#1565C0")
    ax_e.plot(ns_e, means_e, "o-", color="#1565C0", linewidth=2.5,
              markersize=7, markerfacecolor="white", markeredgewidth=2.2, zorder=5)
    ax_e.axhline(0.95, color="#E53935", linestyle="--", linewidth=1.3, alpha=0.85, label="ρ=0.95")
    ax_e.axvline(60,   color="#E53935", linestyle=":", linewidth=1.3, alpha=0.85)
    for n_e, m_e in zip(ns_e, means_e):
        ax_e.annotate(f"{m_e:.2f}", xy=(n_e, m_e), xytext=(n_e + 1, m_e - 0.04),
                      fontsize=9.5, fontweight="bold", color="#1565C0")
    ax_e.set_xlabel("Number of Questions", fontsize=10)
    ax_e.set_ylabel("Spearman ρ vs. Full Ranking", fontsize=10)
    ax_e.set_title("(E) Question Count Sensitivity\n(Spearman ρ vs. N)", fontsize=11, fontweight="bold")
    ax_e.set_xlim(5, 85)
    ax_e.set_ylim(0.0, 1.12)
    ax_e.set_xticks(ns_e)
    ax_e.legend(fontsize=9.5, framealpha=0.85)
    ax_e.grid(True, linestyle="--", alpha=0.4)
    ax_e.set_axisbelow(True)

    fig.suptitle("MT-Bench Reproduction — Phase 1 / 2 / 3 Summary",
                 fontsize=16, fontweight="bold", y=1.01)

    out = FIGURES_DIR / "mt_bench_summary.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ─────────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print(f"Generating figures → {FIGURES_DIR}/")
    fig_category_heatmap()
    fig_overall_rankings()
    fig_hard_easy_gap()
    fig_judge_scaling()
    fig_phase3_scores()
    fig_spearman_heatmap()
    fig_qsize_sensitivity()
    fig_summary_banner()
    print("Done.")


if __name__ == "__main__":
    main()
