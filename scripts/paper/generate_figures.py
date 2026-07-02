#!/usr/bin/env python3
"""
Generate KIPS-ready paper figures and copy-ready result tables.

The script uses committed aggregate CSVs for most panels and raw judge JSONL
files for the reference-guided turn-2 comparison so every judge family can be
reported with the same scoring rule.

Usage:
    python3 scripts/paper/generate_figures.py
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle


ROOT = Path(__file__).resolve().parents[2]
FIG_OUT = ROOT / "paper" / "figures"
TABLE_OUT = ROOT / "paper" / "tables"
FIG_OUT.mkdir(parents=True, exist_ok=True)
TABLE_OUT.mkdir(parents=True, exist_ok=True)

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

RAW_JUDGE_DIRS = {
    ("EN", "Qwen-7B"): ROOT / "data/en/judgments/qwen/judge_7B",
    ("EN", "Qwen-14B"): ROOT / "data/en/judgments/qwen/judge_14B",
    ("EN", "Qwen-32B"): ROOT / "data/en/judgments/qwen/judge_32B",
    ("EN", "EXAONE-32B"): ROOT / "data/en/judgments/exaone/judge_32B",
    ("EN", "GPT-4o-mini"): ROOT / "data/en/judgments/gpt/judge_gpt4omini",
    ("KO", "Qwen-7B"): ROOT / "data/ko/judgments/qwen/judge_7B",
    ("KO", "Qwen-14B"): ROOT / "data/ko/judgments/qwen/judge_14B",
    ("KO", "Qwen-32B"): ROOT / "data/ko/judgments/qwen/judge_32B",
    ("KO", "EXAONE-32B"): ROOT / "data/ko/judgments/exaone/judge_32B",
    ("KO", "GPT-4o-mini"): ROOT / "data/ko/judgments/gpt/judge_gpt4omini",
}

MODEL_LABELS = {
    "EXAONE-3.5-7.8B-Instruct": "EXAONE-7.8B",
    "EEVE-Korean-Instruct-10.8B": "EEVE-10.8B",
    "gemma-2-9b-it": "Gemma-9B",
    "Llama-3.1-8B-Instruct": "Llama-8B",
    "Mistral-7B-Instruct-v0.3": "Mistral-7B",
    "Phi-3.5-mini-Instruct": "Phi-3.5",
}

JUDGE_LABELS = {
    "qwen_7B": "Qwen-7B",
    "qwen_14B": "Qwen-14B",
    "qwen_32B": "Qwen-32B",
    "exaone_32B": "EXAONE-32B",
    "gpt4omini": "GPT-4o-mini",
}

MONO = {
    "black": "#111111",
    "dark": "#333333",
    "mid": "#777777",
    "light": "#D9D9D9",
    "pale": "#F3F3F3",
    "accent": "#555555",
}

PALETTE = {
    "ink": "#1F2933",
    "muted": "#5B6472",
    "rule": "#C9D2DC",
    "panel": "#F6F8FA",
    "blue": "#2F6F9F",
    "blue_light": "#EAF3FA",
    "teal": "#1F9A8A",
    "teal_light": "#E7F5F2",
    "orange": "#D8762D",
    "orange_light": "#FFF1E5",
    "red": "#C54A45",
    "red_light": "#FBEAEA",
    "purple": "#725CA8",
    "purple_light": "#F0ECF8",
    "green": "#4D8C57",
    "green_light": "#EAF5EA",
    "gray_light": "#F4F5F7",
}


def setup_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.edgecolor": MONO["black"],
            "axes.linewidth": 0.8,
            "axes.grid": False,
            "figure.dpi": 140,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "savefig.facecolor": "white",
            "font.size": 8.5,
            "axes.titlesize": 9.5,
            "axes.labelsize": 9,
            "xtick.labelsize": 7.8,
            "ytick.labelsize": 7.8,
            "legend.fontsize": 8,
        }
    )


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def save(fig: plt.Figure, stem: str) -> None:
    png = FIG_OUT / f"{stem}.png"
    pdf = FIG_OUT / f"{stem}.pdf"
    fig.savefig(png)
    fig.savefig(pdf)
    plt.close(fig)
    print(f"saved {png.relative_to(ROOT)}")
    print(f"saved {pdf.relative_to(ROOT)}")


def add_panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(
        -0.08,
        1.05,
        label,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=10,
        fontweight="bold",
    )


def rounded_box(
    ax: plt.Axes,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    fc: str = "white",
    ec: str = PALETTE["rule"],
    lw: float = 0.9,
    radius: float = 0.08,
    zorder: int = 1,
) -> FancyBboxPatch:
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0.015,rounding_size={radius}",
        facecolor=fc,
        edgecolor=ec,
        linewidth=lw,
        zorder=zorder,
    )
    ax.add_patch(patch)
    return patch


def arrow(
    ax: plt.Axes,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    color: str = PALETTE["muted"],
    lw: float = 1.1,
    style: str = "-|>",
    mutation_scale: float = 10,
    rad: float = 0,
    ls: str = "-",
    zorder: int = 6,
) -> None:
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1),
            (x2, y2),
            arrowstyle=style,
            mutation_scale=mutation_scale,
            linewidth=lw,
            color=color,
            linestyle=ls,
            connectionstyle=f"arc3,rad={rad}",
            zorder=zorder,
        )
    )


def phase_panel(ax: plt.Axes, x: float, y: float, w: float, h: float, phase: str, title: str, color: str) -> None:
    header_h = 0.72
    rounded_box(ax, x, y, w, h, fc="white", ec="#AEB8C2", lw=1.0, radius=0.10, zorder=0)
    header = FancyBboxPatch(
        (x, y + h - header_h),
        w,
        header_h,
        boxstyle="round,pad=0.015,rounding_size=0.10",
        facecolor=color,
        edgecolor="#AEB8C2",
        linewidth=1.0,
        zorder=1,
    )
    ax.add_patch(header)
    ax.add_patch(
        Rectangle(
            (x, y + h - header_h),
            w,
            0.31,
            facecolor=color,
            edgecolor="none",
            zorder=2,
        )
    )
    ax.text(x + w / 2, y + h - 0.23, phase, ha="center", va="center", fontsize=6.9, fontweight="bold", color=PALETTE["muted"], zorder=3)
    ax.text(x + w / 2, y + h - 0.50, title, ha="center", va="center", fontsize=7.9, fontweight="bold", color=PALETTE["ink"], zorder=3)


def mini_card(
    ax: plt.Axes,
    x: float,
    y: float,
    w: float,
    h: float,
    label: str,
    *,
    badge: str | None = None,
    fc: str = "white",
    ec: str = PALETTE["rule"],
    color: str = PALETTE["blue"],
    fontsize: float = 7.2,
    zorder: int = 4,
) -> None:
    rounded_box(ax, x, y, w, h, fc=fc, ec=ec, lw=0.9, radius=0.06, zorder=zorder)
    if badge:
        rounded_box(ax, x + 0.10, y + h - 0.30, 0.48, 0.20, fc=color, ec=color, lw=0.0, radius=0.04, zorder=zorder + 1)
        ax.text(x + 0.34, y + h - 0.20, badge, ha="center", va="center", fontsize=5.8, color="white", fontweight="bold", zorder=zorder + 2)
    ax.text(x + w / 2, y + h / 2 - (0.05 if badge else 0), label, ha="center", va="center", fontsize=fontsize, color=PALETTE["ink"], linespacing=1.05, zorder=zorder + 2)


def doc_stack(ax: plt.Axes, x: float, y: float, w: float, h: float, label: str, *, badge: str, color: str) -> None:
    for dx, dy in [(0.08, 0.08), (0.04, 0.04), (0, 0)]:
        rounded_box(ax, x + dx, y - dy, w, h, fc="white", ec="#B6C0CB", lw=0.8, radius=0.05, zorder=3)
    mini_card(ax, x, y, w, h, label, badge=badge, color=color, fontsize=6.9, zorder=5)


def fig1_protocol() -> None:
    fig, ax = plt.subplots(figsize=(8.8, 3.85))
    ax.set_axis_off()
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 7)

    phase_panel(ax, 0.25, 0.78, 3.55, 5.82, "Phase 1", "Benchmark construction", PALETTE["blue_light"])
    phase_panel(ax, 4.15, 0.78, 3.25, 5.82, "Phase 2", "Answer generation", PALETTE["teal_light"])
    phase_panel(ax, 7.75, 0.78, 4.15, 5.82, "Phase 3", "LLM-as-a-judge", PALETTE["purple_light"])
    phase_panel(ax, 12.25, 0.78, 3.50, 5.82, "Phase 4", "Reliability audit", PALETTE["orange_light"])

    # Phase 1: benchmark construction.
    doc_stack(ax, 0.65, 4.65, 1.30, 1.02, "MT-Bench\n80 EN items", badge="EN", color=PALETTE["blue"])
    mini_card(ax, 2.25, 4.62, 1.15, 1.05, "Manual\nKO translation", badge="KO", color=PALETTE["red"], fc="#FFFDFB")
    mini_card(ax, 1.36, 2.93, 1.50, 0.78, "Back-translation\nvalidity check", fc=PALETTE["gray_light"], ec="#B6C0CB", fontsize=6.8)
    rounded_box(ax, 0.78, 1.42, 2.48, 0.82, fc="#FAFBFC", ec="#B6C0CB", lw=0.9, radius=0.06, zorder=4)
    ax.plot([2.02, 2.02], [1.51, 2.15], color="#D4DCE4", lw=0.8, zorder=6)
    ax.text(1.40, 1.86, "EN prompt", ha="center", va="center", fontsize=6.7, color=PALETTE["ink"], zorder=7)
    ax.text(2.64, 1.86, "KO prompt", ha="center", va="center", fontsize=6.7, color=PALETTE["ink"], zorder=7)
    arrow(ax, 1.97, 5.15, 2.23, 5.15, color=PALETTE["blue"])
    arrow(ax, 2.86, 4.62, 2.40, 3.73, color=PALETTE["muted"], rad=-0.18)
    arrow(ax, 2.05, 2.93, 2.02, 2.25, color=PALETTE["muted"], rad=0.08)

    # Phase 2: answer generation.
    rounded_box(ax, 4.55, 4.57, 1.42, 1.08, fc="white", ec="#B6C0CB", lw=0.9, radius=0.06, zorder=4)
    ax.text(5.26, 5.43, "6 evaluated LLMs", ha="center", va="center", fontsize=6.9, fontweight="bold", color=PALETTE["ink"], zorder=7)
    model_names = ["EXAONE", "EEVE", "Gemma", "Llama", "Mistral", "Phi"]
    for i, name in enumerate(model_names):
        yy = 5.18 - i * 0.13
        ax.add_patch(Rectangle((4.77, yy - 0.035), 0.98, 0.065, facecolor="#E8EEF4", edgecolor="none", zorder=6))
        ax.text(5.26, yy, name, ha="center", va="center", fontsize=5.4, color=PALETTE["muted"], zorder=7)
    mini_card(ax, 4.42, 2.93, 1.08, 0.85, "English\nanswers", badge="EN", color=PALETTE["blue"], fc="#FBFDFF", fontsize=6.8)
    mini_card(ax, 5.93, 2.93, 1.08, 0.85, "Korean\nanswers", badge="KO", color=PALETTE["red"], fc="#FFFDFB", fontsize=6.8)
    arrow(ax, 5.25, 4.57, 4.98, 3.80, color=PALETTE["teal"], rad=0.12)
    arrow(ax, 5.42, 4.57, 6.34, 3.80, color=PALETTE["teal"], rad=-0.16)
    rounded_box(ax, 4.72, 1.48, 2.10, 0.78, fc=PALETTE["teal_light"], ec="#A7CEC8", lw=0.9, radius=0.06, zorder=4)
    ax.text(5.77, 1.86, "EN/KO response pairs", ha="center", va="center", fontsize=7.1, fontweight="bold", color=PALETTE["ink"], zorder=7)
    arrow(ax, 4.96, 2.93, 5.45, 2.27, color=PALETTE["teal"], rad=0.08)
    arrow(ax, 6.45, 2.93, 6.02, 2.27, color=PALETTE["teal"], rad=-0.08)

    # Phase 3: judge settings and modes.
    rounded_box(ax, 8.18, 4.48, 1.22, 1.16, fc="white", ec="#B6C0CB", lw=0.9, radius=0.06, zorder=4)
    ax.text(8.79, 5.41, "Same-family", ha="center", va="center", fontsize=6.4, fontweight="bold", color=PALETTE["ink"], zorder=7)
    for i, (name, width) in enumerate([("Qwen-7B", 0.58), ("Qwen-14B", 0.80), ("Qwen-32B", 1.00)]):
        yy = 5.14 - i * 0.22
        ax.add_patch(Rectangle((8.29, yy - 0.055), width, 0.11, facecolor=PALETTE["purple_light"], edgecolor=PALETTE["purple"], lw=0.5, zorder=6))
        ax.text(8.86, yy, name, ha="center", va="center", fontsize=5.6, color=PALETTE["ink"], zorder=7)
    mini_card(ax, 10.02, 4.48, 1.32, 1.16, "EXAONE-32B\nGPT-4o-mini", badge="CF", color=PALETTE["purple"], fc="#FEFCFF", fontsize=6.4)
    rounded_box(ax, 8.22, 2.82, 3.06, 1.00, fc="#FBFAFE", ec="#BEB3DA", lw=0.9, radius=0.06, zorder=4)
    ax.text(9.75, 3.55, "Judge modes", ha="center", va="center", fontsize=6.8, fontweight="bold", color=PALETTE["ink"], zorder=7)
    mode_x = [8.42, 9.34, 10.26]
    mode_labels = ["Single\ngrade", "Pairwise\nAB/BA", "Reference\nguided"]
    for mx, label in zip(mode_x, mode_labels):
        rounded_box(ax, mx, 3.02, 0.78, 0.38, fc="white", ec="#CBBFE0", lw=0.7, radius=0.04, zorder=6)
        ax.text(mx + 0.39, 3.21, label, ha="center", va="center", fontsize=5.7, color=PALETTE["ink"], linespacing=0.92, zorder=7)
    # Small balance icon.
    ax.plot([9.75, 9.75], [1.56, 2.20], color=PALETTE["purple"], lw=1.1, zorder=7)
    ax.plot([9.28, 10.22], [2.02, 2.02], color=PALETTE["purple"], lw=1.1, zorder=7)
    ax.add_patch(Polygon([[9.25, 1.72], [9.48, 1.72], [9.37, 1.50]], closed=True, facecolor="white", edgecolor=PALETTE["purple"], lw=0.8, zorder=7))
    ax.add_patch(Polygon([[10.02, 1.72], [10.25, 1.72], [10.14, 1.50]], closed=True, facecolor="white", edgecolor=PALETTE["purple"], lw=0.8, zorder=7))
    ax.text(9.75, 1.22, "score / choice / parse", ha="center", va="center", fontsize=6.5, color=PALETTE["muted"], zorder=7)
    arrow(ax, 8.79, 4.48, 9.42, 3.83, color=PALETTE["purple"], rad=0.10)
    arrow(ax, 10.68, 4.48, 10.06, 3.83, color=PALETTE["purple"], rad=-0.10)

    # Phase 4: reliability audit.
    metric_cards = [
        (12.56, 4.62, "Score gap", "EN vs. KO", PALETTE["blue"], PALETTE["blue_light"]),
        (14.05, 4.62, "AB/BA", "inconsistency", PALETTE["purple"], PALETTE["purple_light"]),
        (12.56, 3.18, "1st-pos", "bias share", PALETTE["orange"], PALETTE["orange_light"]),
        (14.05, 3.18, "Parse", "failure", PALETTE["red"], PALETTE["red_light"]),
    ]
    for x, y, title, subtitle, color, fill in metric_cards:
        rounded_box(ax, x, y, 1.15, 0.95, fc=fill, ec=color, lw=0.9, radius=0.06, zorder=4)
        ax.text(x + 0.58, y + 0.62, title, ha="center", va="center", fontsize=7.0, fontweight="bold", color=PALETTE["ink"], zorder=7)
        ax.text(x + 0.58, y + 0.32, subtitle, ha="center", va="center", fontsize=5.8, color=PALETTE["muted"], zorder=7)
    # Tiny chart glyphs make the metrics read as outputs, not more boxes.
    ax.plot([12.77, 13.02, 13.22], [4.83, 4.98, 4.76], color=PALETTE["blue"], lw=1.2, zorder=8)
    arrow(ax, 14.26, 4.85, 14.68, 4.85, color=PALETTE["purple"], mutation_scale=7, lw=0.9)
    arrow(ax, 14.68, 4.71, 14.26, 4.71, color=PALETTE["purple"], mutation_scale=7, lw=0.9)
    ax.text(12.95, 3.62, "A", ha="center", va="center", fontsize=8, color=PALETTE["orange"], fontweight="bold", zorder=8)
    ax.text(13.28, 3.62, "B", ha="center", va="center", fontsize=8, color="#9A9A9A", zorder=8)
    ax.text(14.62, 3.62, "!", ha="center", va="center", fontsize=12, color=PALETTE["red"], fontweight="bold", zorder=8)
    rounded_box(ax, 12.82, 1.46, 2.40, 0.82, fc="white", ec="#B6C0CB", lw=0.9, radius=0.06, zorder=4)
    ax.text(14.02, 1.84, "Raw JSONL + aggregate CSV", ha="center", va="center", fontsize=7.0, fontweight="bold", color=PALETTE["ink"], zorder=7)
    ax.text(14.02, 1.57, "audit and recomputation", ha="center", va="center", fontsize=5.9, color=PALETTE["muted"], zorder=7)
    arrow(ax, 13.13, 3.18, 13.57, 2.30, color=PALETTE["orange"], rad=0.14)
    arrow(ax, 14.62, 3.18, 14.38, 2.30, color=PALETTE["red"], rad=-0.10)

    # Cross-panel flow.
    arrow(ax, 3.80, 3.48, 4.15, 3.48, color=PALETTE["muted"], lw=1.2, mutation_scale=12)
    arrow(ax, 7.40, 3.48, 7.75, 3.48, color=PALETTE["muted"], lw=1.2, mutation_scale=12)
    arrow(ax, 11.90, 3.48, 12.25, 3.48, color=PALETTE["muted"], lw=1.2, mutation_scale=12)
    ax.text(8.0, 0.33, "All figures are generated from committed aggregate CSVs and raw pairwise/single/reference judgment JSONL files.", ha="center", va="center", fontsize=6.9, color=PALETTE["muted"])

    fig.tight_layout(pad=0.1)
    save(fig, "fig1_protocol")

def qwen32_gap_frame() -> pd.DataFrame:
    en = read_csv(SCORE_FILES[("EN", "Qwen-32B")])
    ko = read_csv(SCORE_FILES[("KO", "Qwen-32B")])

    df = en[["model", "overall", "n_samples"]].merge(
        ko[["model", "overall", "n_samples"]], on="model", suffixes=("_en", "_ko")
    )
    df["gap"] = df["overall_ko"] - df["overall_en"]
    df["label"] = df["model"].map(MODEL_LABELS)
    return df.sort_values("gap")


def fig2_score_gap() -> None:
    df = qwen32_gap_frame()
    df = df.sort_values("overall_en", ascending=True).reset_index(drop=True)
    y = np.arange(len(df))

    fig, ax = plt.subplots(figsize=(7.2, 3.45))
    for idx, row in enumerate(df.itertuples(index=False)):
        gap_abs = abs(row.gap)
        line_color = PALETTE["red"] if gap_abs >= 1.5 else PALETTE["orange"] if gap_abs >= 0.7 else PALETTE["green"]
        ax.hlines(idx, row.overall_ko, row.overall_en, color=line_color, alpha=0.42, lw=3.2, zorder=1)
        ax.plot(row.overall_en, idx, "o", ms=6.2, mfc="white", mec=PALETTE["blue"], mew=1.3, zorder=4)
        ax.plot(row.overall_ko, idx, "s", ms=5.8, mfc=PALETTE["red"], mec=PALETTE["red"], mew=0.8, zorder=4)
        gap_fc = PALETTE["red_light"] if gap_abs >= 1.5 else PALETTE["orange_light"] if gap_abs >= 0.7 else PALETTE["green_light"]
        ax.text(
            8.66,
            idx,
            f"{row.gap:+.2f}",
            ha="center",
            va="center",
            fontsize=7.2,
            fontweight="bold",
            color=PALETTE["ink"],
            bbox=dict(boxstyle="round,pad=0.22,rounding_size=0.10", fc=gap_fc, ec="none"),
            zorder=5,
        )
    ax.set_yticks(y)
    ax.set_yticklabels(df["label"])
    ax.set_xlabel("MT-Bench score (1-10)")
    ax.set_xlim(4.2, 8.9)
    ax.set_title("Qwen-32B judge: English and Korean single-grade scores", loc="left", fontsize=9.4, fontweight="bold")
    ax.grid(axis="x", color="#E6EAF0", lw=0.65)
    ax.set_axisbelow(True)
    ax.text(8.66, len(df) - 0.15, "KO-EN", ha="center", va="bottom", fontsize=7.2, fontweight="bold", color=PALETTE["muted"])
    legend_handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor="white", markeredgecolor=PALETTE["blue"], markeredgewidth=1.3, markersize=6, label="EN"),
        Line2D([0], [0], marker="s", color="none", markerfacecolor=PALETTE["red"], markeredgecolor=PALETTE["red"], markersize=5.8, label="KO"),
    ]
    ax.legend(handles=legend_handles, frameon=False, loc="lower right", bbox_to_anchor=(0.97, 0.03), ncol=2, handletextpad=0.35, columnspacing=0.85)
    ax.text(0.0, -0.19, "Gap chips report Korean minus English score; larger red gaps indicate stronger cross-lingual degradation.", transform=ax.transAxes, fontsize=7.0, color=PALETTE["muted"])
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_color("#AEB8C2")
    save(fig, "fig2_score_gap_qwen32")


def fig3_reliability_bias() -> None:
    comp = read_csv(ROOT / "data/ko/results/results_en_ko_comparison.csv")
    comp["judge_label"] = comp["judge"].map(JUDGE_LABELS)
    comp["en_fp_in_incon"] = comp["en_fp_pct"] / comp["en_incon_pct"] * 100
    comp["ko_fp_in_incon"] = comp["ko_fp_pct"] / comp["ko_incon_pct"] * 100

    colors = {
        "qwen_7B": PALETTE["blue"],
        "qwen_14B": PALETTE["teal"],
        "qwen_32B": PALETTE["green"],
        "exaone_32B": PALETTE["orange"],
        "gpt4omini": PALETTE["purple"],
    }
    offsets = {
        "qwen_7B": (1.4, 0.8),
        "qwen_14B": (1.0, -3.8),
        "qwen_32B": (1.0, 2.0),
        "exaone_32B": (1.0, 1.8),
        "gpt4omini": (1.0, -2.8),
    }

    fig, ax = plt.subplots(figsize=(7.15, 4.0))
    ax.add_patch(Rectangle((15, 20), 20, 30, facecolor=PALETTE["green_light"], edgecolor="none", alpha=0.75, zorder=0))
    ax.text(17.0, 24.5, "lower\nrisk", ha="left", va="bottom", fontsize=7.0, color=PALETTE["green"], fontweight="bold", zorder=1)
    ax.axhline(50, color="#9AA6B2", lw=0.9, ls=":", zorder=1)
    ax.text(84.5, 51.8, "no 1st-position preference", ha="right", va="bottom", fontsize=6.8, color=PALETTE["muted"])

    for row in comp.itertuples(index=False):
        color = colors[row.judge]
        ax.plot(
            [row.en_incon_pct, row.ko_incon_pct],
            [row.en_fp_in_incon, row.ko_fp_in_incon],
            color=color,
            lw=1.3,
            alpha=0.55,
            zorder=2,
        )
        ax.scatter(row.en_incon_pct, row.en_fp_in_incon, s=52, marker="o", facecolor="white", edgecolor=color, linewidth=1.3, zorder=4)
        ax.scatter(row.ko_incon_pct, row.ko_fp_in_incon, s=48, marker="s", facecolor=color, edgecolor=color, linewidth=0.8, zorder=4)
        dx, dy = offsets[row.judge]
        ax.text(
            row.ko_incon_pct + dx,
            row.ko_fp_in_incon + dy,
            row.judge_label,
            ha="left",
            va="center",
            fontsize=7.0,
            color=PALETTE["ink"],
            bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.78),
            zorder=5,
        )

    ax.annotate(
        "Qwen scale-up\nreduces inconsistency",
        xy=(30.9, 72.0),
        xytext=(48, 37),
        arrowprops=dict(arrowstyle="->", color=PALETTE["blue"], lw=0.9, connectionstyle="arc3,rad=-0.20"),
        fontsize=7.0,
        color=PALETTE["blue"],
        ha="left",
    )
    ax.set_xlim(15, 85)
    ax.set_ylim(20, 100)
    ax.set_xlabel("AB/BA inconsistency (%)")
    ax.set_ylabel("First-position share within inconsistent pairs (%)")
    ax.set_title("Pairwise judge reliability map", loc="left", fontsize=9.4, fontweight="bold")
    ax.grid(color="#E6EAF0", lw=0.65)
    ax.set_axisbelow(True)
    handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor="white", markeredgecolor=PALETTE["ink"], markeredgewidth=1.2, markersize=6, label="EN"),
        Line2D([0], [0], marker="s", color="none", markerfacecolor=PALETTE["ink"], markeredgecolor=PALETTE["ink"], markersize=6, label="KO"),
    ]
    ax.legend(handles=handles, frameon=False, loc="lower right", ncol=2, handletextpad=0.35, columnspacing=0.9)
    ax.text(0.0, -0.18, "Each segment connects the English and Korean result for the same judge setting.", transform=ax.transAxes, fontsize=7.0, color=PALETTE["muted"])
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_color("#AEB8C2")
    fig.tight_layout()
    save(fig, "fig3_reliability_bias")


def valid_score(value: object) -> bool:
    return isinstance(value, (int, float)) and value > 0


def load_turn2_scores(path: Path) -> list[float]:
    scores = []
    if not path.exists():
        return scores
    with path.open(encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            score = d.get("score_turn2", -1.0)
            if valid_score(score):
                scores.append(float(score))
    return scores


def collect_ref_score_diff() -> pd.DataFrame:
    rows = []
    model_ids = list(MODEL_LABELS.keys())
    for (lang, judge), judge_dir in RAW_JUDGE_DIRS.items():
        nonref_scores = []
        ref_scores = []
        for model_id in model_ids:
            nonref_scores.extend(load_turn2_scores(judge_dir / "single_grade" / f"{model_id}.jsonl"))
            ref_scores.extend(load_turn2_scores(judge_dir / "single_grade_ref" / f"{model_id}.jsonl"))
        if not nonref_scores or not ref_scores:
            continue
        nonref_mean = float(np.mean(nonref_scores))
        ref_mean = float(np.mean(ref_scores))
        rows.append(
            {
                "lang": lang,
                "judge": judge,
                "n_nonref": len(nonref_scores),
                "nonref_mean": nonref_mean,
                "n_ref": len(ref_scores),
                "ref_mean": ref_mean,
                "diff_ref_minus_nonref": ref_mean - nonref_mean,
            }
        )
    return pd.DataFrame(rows)


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


def reference_parse_summary() -> pd.DataFrame:
    coverage = collect_parse_coverage()
    order = {key: idx for idx, key in enumerate(RAW_JUDGE_DIRS)}
    ref_parse = (
        coverage[coverage["type"] == "reference"]
        .groupby(["lang", "judge"], as_index=False)
        .agg(valid=("valid", "sum"), expected=("expected", "sum"))
        .assign(failure_rate=lambda d: 1 - d["valid"] / d["expected"])
    )
    ref_parse["order"] = ref_parse.apply(lambda row: order[(row["lang"], row["judge"])], axis=1)
    return ref_parse.sort_values("order")


def fig4_ref_parse() -> None:
    ref = collect_ref_score_diff()
    ref_parse = reference_parse_summary()

    judge_order = ["Qwen-7B", "Qwen-14B", "Qwen-32B", "EXAONE-32B", "GPT-4o-mini"]
    judge_short = ["Qwen\n7B", "Qwen\n14B", "Qwen\n32B", "EXAONE\n32B", "GPT-4o\nmini"]
    lang_order = ["EN", "KO"]
    ref_mat = np.full((len(lang_order), len(judge_order)), np.nan)
    parse_mat = np.full_like(ref_mat, np.nan, dtype=float)

    for row in ref.itertuples(index=False):
        i = lang_order.index(row.lang)
        j = judge_order.index(row.judge)
        ref_mat[i, j] = row.diff_ref_minus_nonref
    for row in ref_parse.itertuples(index=False):
        i = lang_order.index(row.lang)
        j = judge_order.index(row.judge)
        parse_mat[i, j] = row.failure_rate * 100

    fig, axes = plt.subplots(1, 2, figsize=(8.8, 2.85), gridspec_kw={"wspace": 0.22})

    ax = axes[0]
    im = ax.imshow(-ref_mat, cmap="OrRd", vmin=0, vmax=max(2.6, float(np.nanmax(-ref_mat))), aspect="auto")
    ax.set_title("(a) Reference-guided score drop", loc="left", fontsize=9.0, fontweight="bold")
    ax.set_xticks(np.arange(len(judge_order)))
    ax.set_xticklabels(judge_short, fontsize=7.2)
    ax.set_yticks(np.arange(len(lang_order)))
    ax.set_yticklabels(lang_order, fontsize=8.0, fontweight="bold")
    ax.tick_params(length=0)
    for i in range(len(lang_order)):
        for j in range(len(judge_order)):
            val = ref_mat[i, j]
            ax.text(j, i, f"{val:+.2f}", ha="center", va="center", fontsize=7.5, color=PALETTE["ink"], fontweight="bold")
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xlabel("judge setting", labelpad=5)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    cbar.set_label("absolute drop", fontsize=7)
    cbar.ax.tick_params(labelsize=6.5, length=2)

    ax = axes[1]
    im2 = ax.imshow(parse_mat, cmap="YlOrRd", vmin=0, vmax=max(34, float(np.nanmax(parse_mat))), aspect="auto")
    ax.set_title("(b) Reference parse failure", loc="left", fontsize=9.0, fontweight="bold")
    ax.set_xticks(np.arange(len(judge_order)))
    ax.set_xticklabels(judge_short, fontsize=7.2)
    ax.set_yticks(np.arange(len(lang_order)))
    ax.set_yticklabels(lang_order, fontsize=8.0, fontweight="bold")
    ax.tick_params(length=0)
    for i in range(len(lang_order)):
        for j in range(len(judge_order)):
            val = parse_mat[i, j]
            label = f"{val:.1f}%"
            color = "white" if val >= 20 else PALETTE["ink"]
            ax.text(j, i, label, ha="center", va="center", fontsize=7.5, color=color, fontweight="bold")
    ax.add_patch(Rectangle((-0.49, 0.51), 0.98, 0.98, fill=False, edgecolor=PALETTE["red"], linewidth=2.0, zorder=4))
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xlabel("judge setting", labelpad=5)
    cbar2 = fig.colorbar(im2, ax=ax, fraction=0.046, pad=0.03)
    cbar2.set_label("failure rate (%)", fontsize=7)
    cbar2.ax.tick_params(labelsize=6.5, length=2)

    fig.subplots_adjust(left=0.07, right=0.95, top=0.84, bottom=0.24, wspace=0.26)
    save(fig, "fig4_ref_parse_failure")


def write_tables() -> None:
    gap = qwen32_gap_frame().copy()
    gap["Model"] = gap["label"]
    gap["EN"] = gap["overall_en"].map(lambda x: f"{x:.2f}")
    gap["KO"] = gap["overall_ko"].map(lambda x: f"{x:.2f}")
    gap["KO-EN"] = gap["gap"].map(lambda x: f"{x:+.2f}")

    comp = read_csv(ROOT / "data/ko/results/results_en_ko_comparison.csv").copy()
    comp["Judge"] = comp["judge"].map(JUDGE_LABELS)
    comp["EN inconsistency"] = comp["en_incon_pct"].map(lambda x: f"{x:.1f}%")
    comp["KO inconsistency"] = comp["ko_incon_pct"].map(lambda x: f"{x:.1f}%")
    comp["Delta"] = comp["delta_incon_pct"].map(lambda x: f"{x:+.1f} pp")
    comp["EN first-pos/incon"] = (comp["en_fp_pct"] / comp["en_incon_pct"] * 100).map(lambda x: f"{x:.0f}%")
    comp["KO first-pos/incon"] = (comp["ko_fp_pct"] / comp["ko_incon_pct"] * 100).map(lambda x: f"{x:.0f}%")

    ref = collect_ref_score_diff().copy()
    ref["Lang"] = ref["lang"]
    ref["Judge"] = ref["judge"]
    ref["Non-ref"] = ref["nonref_mean"].map(lambda x: f"{float(x):.2f}")
    ref["Ref"] = ref["ref_mean"].map(lambda x: f"{float(x):.2f}")
    ref["Ref - non-ref"] = ref["diff_ref_minus_nonref"].map(lambda x: f"{float(x):+.2f}")

    ref_parse = reference_parse_summary().copy()
    ref_parse["Lang"] = ref_parse["lang"]
    ref_parse["Judge"] = ref_parse["judge"]
    ref_parse["Failed"] = (ref_parse["expected"] - ref_parse["valid"]).map(lambda x: f"{int(round(x))}")
    ref_parse["Total"] = ref_parse["expected"].map(lambda x: f"{int(round(x))}")
    ref_parse["Failure rate"] = ref_parse["failure_rate"].map(lambda x: f"{x * 100:.1f}%")

    content = "# KIPS-ready Copy Tables\n\n"
    content += "## Table 1. Qwen-32B EN-KO single-grade score gap\n\n"
    content += gap[["Model", "EN", "KO", "KO-EN"]].to_markdown(index=False, disable_numparse=True)
    content += "\n\n## Table 2. Inconsistency and first-position tendency\n\n"
    content += comp[
        [
            "Judge",
            "EN inconsistency",
            "KO inconsistency",
            "Delta",
            "EN first-pos/incon",
            "KO first-pos/incon",
        ]
    ].to_markdown(index=False, disable_numparse=True)
    content += "\n\n## Table 3. Reference-guided score difference by judge\n\n"
    content += ref[["Lang", "Judge", "Non-ref", "Ref", "Ref - non-ref"]].to_markdown(
        index=False, disable_numparse=True
    )
    content += "\n\n## Table 4. Reference-guided parse failure by judge\n\n"
    content += ref_parse[["Lang", "Judge", "Failed", "Total", "Failure rate"]].to_markdown(
        index=False, disable_numparse=True
    )
    content += "\n"

    path = TABLE_OUT / "kci_tables.md"
    path.write_text(content, encoding="utf-8")
    print(f"saved {path.relative_to(ROOT)}")


def write_notes() -> None:
    notes = dedent(
        """
        # KIPS Paper Artifacts

        이 도표 세트는 KIPS 정보처리학회논문지 투고 원고에 맞춰 본문 삽입용으로 설계했다.
        색 의존도를 줄이고, 흑백 인쇄에서도 구분되도록 marker shape, line style, hatch를 사용한다.

        ## Regeneration

        ```bash
        python3 scripts/paper/generate_figures.py
        ```

        Generated outputs:

        - `paper/figures/*.png`
        - `paper/figures/*.pdf`
        - `paper/tables/kci_tables.md`

        ## Suggested Figure Order

        1. **Fig. 1. Experimental protocol.**
           방법론 섹션 마지막 또는 실험 설계 첫 부분에 배치한다.
        2. **Fig. 2. Qwen-32B single-grade score gap.**
           핵심 결과 1: 범용 영어 모델의 KO 하락폭과 한국어 특화 모델의 완충 효과.
        3. **Fig. 3. Pairwise inconsistency and residual position tendency.**
           핵심 결과 2: judge reliability와 position-sensitive residual error.
        4. **Fig. 4. Reference-guided scoring and parse failure.**
           핵심 결과 3 및 한계: reference 제공 효과와 KO 7B ref parse failure.

        ## Caption Drafts

        - **Fig. 1.** Overview of the Korean MT-Bench evaluation protocol.
        - **Fig. 2.** English and Korean MT-Bench scores under the Qwen-32B judge.
          The annotation denotes the observed KO-EN score gap.
        - **Fig. 3.** Pairwise inconsistency and first-position tendency across judge
          settings. First-position share is computed within inconsistent pairs.
        - **Fig. 4.** Reference-guided scoring effects and reference-guided
          parse-failure rates across all judge settings. Raw JSONL judgments are
          included for independent audit and recomputation.
        """
    ).strip()
    path = ROOT / "paper" / "README.md"
    path.write_text(notes + "\n", encoding="utf-8")
    print(f"saved {path.relative_to(ROOT)}")


def print_audit() -> None:
    coverage = collect_parse_coverage()
    coverage["valid_rate"] = coverage["valid"] / coverage["expected"]
    bad = coverage[coverage["valid_rate"] < 0.995].sort_values("valid_rate")
    print("\ncoverage audit: rows with valid sample coverage < 99.5%")
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
    print(f"Generating KIPS-ready figures under {FIG_OUT.relative_to(ROOT)}/")
    fig1_protocol()
    fig2_score_gap()
    fig3_reliability_bias()
    fig4_ref_parse()
    write_tables()
    write_notes()
    print_audit()


if __name__ == "__main__":
    main()
