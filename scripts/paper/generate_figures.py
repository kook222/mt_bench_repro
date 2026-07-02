#!/usr/bin/env python3
"""
Generate paper-ready figures and copy-ready result tables for domestic KCI/NLP submissions.

The script uses committed aggregate CSVs for most panels and raw judge JSONL
files for the reference-guided turn-2 comparison so every judge family can be
reported with the same scoring rule.

Usage:
    python3 scripts/paper/generate_figures.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle


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

PAPER = {
    "blue": "#2F6F9F",
    "blue_dark": "#24597F",
    "blue_light": "#DCECF7",
    "panel": "#F8FAFC",
    "panel_edge": "#D9E1E8",
    "orange": "#F2A44A",
    "orange_light": "#FFE8C7",
    "red": "#E85B4A",
    "green": "#9AAEAA",
    "green_light": "#E8F0EE",
    "ink": "#111111",
    "muted": "#555555",
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


def flow_arrow(
    ax: plt.Axes,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    color: str = PAPER["blue_dark"],
    lw: float = 1.1,
    scale: float = 12,
) -> None:
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1),
            (x2, y2),
            arrowstyle="-|>",
            mutation_scale=scale,
            linewidth=lw,
            color=color,
            zorder=3,
        )
    )


def text_box(
    ax: plt.Axes,
    x: float,
    y: float,
    w: float,
    h: float,
    text: str,
    *,
    fc: str = "white",
    ec: str = "#8293A3",
    fontsize: float = 5.2,
    weight: str = "normal",
    color: str = "#222222",
    zorder: int = 4,
) -> None:
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.02,rounding_size=0.06",
            facecolor=fc,
            edgecolor=ec,
            linewidth=0.75,
            zorder=zorder,
        )
    )
    ax.text(
        x + w / 2,
        y + h / 2,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        fontweight=weight,
        color=color,
        linespacing=0.95,
        zorder=zorder + 1,
    )


def panel(ax: plt.Axes, x: float, y: float, w: float, h: float, title: str, subtitle: str) -> None:
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.035,rounding_size=0.10",
            facecolor="#FFFFFF",
            edgecolor="#C7D1DA",
            linewidth=0.8,
            zorder=1,
        )
    )
    ax.text(x + 2.8, y + h - 1.55, title, ha="left", va="center", fontsize=6.6, fontweight="bold", color="#111111", zorder=4)
    ax.text(x + 2.8, y + h - 2.70, subtitle, ha="left", va="center", fontsize=4.9, color="#555555", zorder=4)


def step_badge(ax: plt.Axes, x: float, y: float, label: str, color: str) -> None:
    ax.add_patch(Circle((x, y), 0.72, facecolor=color, edgecolor="white", linewidth=0.7, zorder=5))
    ax.text(x, y, label, ha="center", va="center", fontsize=5.8, fontweight="bold", color="white", zorder=6)


def output_tile(ax: plt.Axes, x: float, y: float, w: float, h: float, title: str, value: str, note: str, color: str) -> None:
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.025,rounding_size=0.08",
            facecolor="#FFFFFF",
            edgecolor="#CDD6DE",
            linewidth=0.75,
            zorder=3,
        )
    )
    ax.text(x + 0.75, y + h - 1.05, title, ha="left", va="center", fontsize=5.8, fontweight="bold", color="#222222", zorder=4)
    ax.text(x + 0.75, y + 2.00, value, ha="left", va="center", fontsize=7.2, fontweight="bold", color=color, zorder=4)
    ax.text(x + 0.75, y + 0.85, note, ha="left", va="center", fontsize=4.8, color="#555555", zorder=4)


def raw_judgment_file_count() -> int:
    return sum(1 for root in [ROOT / "data/en/judgments", ROOT / "data/ko/judgments"] for _ in root.rglob("*.jsonl"))


def question_count() -> int:
    path = ROOT / "data/ko/questions.jsonl"
    if not path.exists():
        return 80
    return sum(1 for _ in path.open(encoding="utf-8"))


def fig1_summary_metrics() -> dict[str, str]:
    gap = qwen32_gap_frame()
    min_gap = gap.loc[gap["gap"].idxmin()]

    comp = read_csv(ROOT / "data/ko/results/results_en_ko_comparison.csv").copy()
    comp["judge_label"] = comp["judge"].map(JUDGE_LABELS)
    qwen7 = comp[comp["judge_label"] == "Qwen-7B"].iloc[0]
    qwen32 = comp[comp["judge_label"] == "Qwen-32B"].iloc[0]
    comp["en_fp_in_incon"] = comp["en_fp_pct"] / comp["en_incon_pct"] * 100
    comp["ko_fp_in_incon"] = comp["ko_fp_pct"] / comp["ko_incon_pct"] * 100
    fp_candidates = []
    for row in comp.itertuples(index=False):
        fp_candidates.append((float(row.en_fp_in_incon), "EN", row.judge_label))
        fp_candidates.append((float(row.ko_fp_in_incon), "KO", row.judge_label))
    max_fp, fp_lang, fp_judge = max(fp_candidates, key=lambda item: item[0])

    ref_parse = reference_parse_summary()
    max_parse_row = ref_parse.loc[ref_parse["failure_rate"].idxmax()]
    return {
        "question_count": f"{question_count()}",
        "model_count": f"{len(MODEL_LABELS)}",
        "judge_count": f"{len(JUDGE_LABELS)}",
        "raw_files": f"{raw_judgment_file_count()}",
        "gap_value": f"{float(min_gap.gap):+.2f}",
        "gap_note": f"{min_gap.label} KO-EN",
        "scaling_value": f"{float(qwen7.en_incon_pct):.1f} -> {float(qwen32.en_incon_pct):.1f}%",
        "scaling_note": "Qwen EN incons.",
        "position_value": f"max {max_fp:.0f}%",
        "position_note": f"{fp_lang} {fp_judge}",
        "parse_value": f"{float(max_parse_row.failure_rate * 100):.1f}%",
        "parse_note": f"{max_parse_row.lang} {max_parse_row.judge} ref.",
    }


def fig1_protocol() -> None:
    summary = fig1_summary_metrics()
    fig, ax = plt.subplots(figsize=(8.8, 4.85))
    ax.set_axis_off()
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 56)

    ax.text(3.0, 53.8, "Korean MT-Bench Reliability Audit", ha="left", va="center", fontsize=9.2, fontweight="bold")
    ax.text(
        3.0,
        51.5,
        f"{summary['question_count']} paired prompts -> {summary['model_count']} answer models -> {summary['judge_count']} judge settings -> language, order, and parsing diagnostics",
        ha="left",
        va="center",
        fontsize=5.9,
        color="#555555",
    )

    # Stage 1: paired prompt construction.
    panel(ax, 3, 26.5, 20, 21.5, "Paired prompt set", "parallel EN/KO items")
    step_badge(ax, 5.0, 45.8, "1", PAPER["blue_dark"])
    y_rows = [40.5, 36.5]
    for label, color, yy in [("EN", PAPER["blue_dark"], y_rows[0]), ("KO", PAPER["red"], y_rows[1])]:
        ax.text(6.0, yy + 0.65, label, ha="center", va="center", fontsize=5.7, fontweight="bold", color=color)
        for i in range(3):
            ax.add_patch(Rectangle((8.4 + i * 3.4, yy), 2.1, 1.25, facecolor="#F9FBFD", edgecolor=color, linewidth=0.65, zorder=4))
    text_box(ax, 6.0, 30.0, 14.0, 3.8, f"{summary['question_count']} two-turn items\nmanual translation + back-translation QC", fc="#F7FAFC", ec="#B8C5D0", fontsize=4.8, weight="bold")

    # Stage 2: answer matrix.
    panel(ax, 29, 26.5, 22, 21.5, "Answer matrix", "models x languages")
    step_badge(ax, 31.0, 45.8, "2", PAPER["blue_dark"])
    ax.text(39.4, 41.2, "EN", ha="center", va="center", fontsize=5.2, fontweight="bold", color=PAPER["blue_dark"])
    ax.text(44.1, 41.2, "KO", ha="center", va="center", fontsize=5.2, fontweight="bold", color=PAPER["red"])
    for i, label in enumerate(["EXA", "EEVE", "Gem", "Llama", "Mis", "Phi"]):
        yy = 39.1 - i * 2.05
        ax.text(32.0, yy + 0.55, label, ha="left", va="center", fontsize=4.5, color="#444444")
        ax.add_patch(Rectangle((38.2, yy), 2.5, 1.2, facecolor=PAPER["blue_light"], edgecolor="white", linewidth=0.7, zorder=4))
        ax.add_patch(Rectangle((42.9, yy), 2.5, 1.2, facecolor="#FDE2DF", edgecolor="white", linewidth=0.7, zorder=4))
    ax.text(40.8, 28.2, f"{summary['model_count']} LLMs; responses aligned by item and turn", ha="center", va="center", fontsize=4.8, color="#555555")

    # Stage 3: judge matrix.
    panel(ax, 57, 26.5, 40, 21.5, "Judge and scoring matrix", "judge families x scoring modes")
    step_badge(ax, 59.0, 45.8, "3", PAPER["blue_dark"])
    cols = ["single", "pairwise", "ref."]
    rows = ["Qwen-7B", "Qwen-14B", "Qwen-32B", "EXAONE", "GPT-4o"]
    for j, col in enumerate(cols):
        ax.text(76.0 + j * 6.0, 41.5, col, ha="center", va="center", fontsize=4.8, fontweight="bold", color="#444444")
    for i, row in enumerate(rows):
        yy = 39.0 - i * 2.35
        ax.text(61.0, yy + 0.55, row, ha="left", va="center", fontsize=4.7, color="#444444")
        fc = PAPER["blue_light"] if i < 3 else PAPER["green_light"]
        for j in range(3):
            ax.add_patch(Rectangle((74.8 + j * 6.0, yy), 3.0, 1.25, facecolor=fc, edgecolor="white", linewidth=0.7, zorder=4))
    ax.plot([60.5, 94.5], [31.4, 31.4], color="#D8DEE6", lw=0.7, zorder=3)
    text_box(ax, 66.0, 28.7, 24.5, 2.8, f"{summary['raw_files']} raw judgment files + aggregate CSV tables", fc="#FFF8EC", ec=PAPER["orange"], fontsize=4.8, weight="bold")

    flow_arrow(ax, 23.4, 37.2, 28.4, 37.2, color="#6C7A86", lw=1.0, scale=10)
    flow_arrow(ax, 51.5, 37.2, 56.5, 37.2, color="#6C7A86", lw=1.0, scale=10)
    flow_arrow(ax, 77.0, 26.2, 77.0, 21.8, color="#6C7A86", lw=1.0, scale=10)

    # Stage 4: diagnostics.
    ax.add_patch(
        FancyBboxPatch(
            (3, 5.2),
            94,
            14.6,
            boxstyle="round,pad=0.035,rounding_size=0.12",
            facecolor="#F8FAFC",
            edgecolor="#CDD6DE",
            linewidth=0.8,
            zorder=1,
        )
    )
    step_badge(ax, 5.2, 17.3, "4", PAPER["blue_dark"])
    ax.text(7.2, 17.3, "Reliability readouts recomputed from public raw records", ha="left", va="center", fontsize=6.9, fontweight="bold", zorder=5)
    tile_specs = [
        (6.2, "Language gap", summary["gap_value"], summary["gap_note"]),
        (29.0, "Judge scaling", summary["scaling_value"], summary["scaling_note"]),
        (51.8, "Order tendency", summary["position_value"], summary["position_note"]),
        (74.6, "Parse failure", summary["parse_value"], summary["parse_note"]),
    ]
    colors = [PAPER["red"], PAPER["blue_dark"], PAPER["orange"], "#7A4CC2"]
    for (x, title, value, note), color in zip(tile_specs, colors):
        output_tile(ax, x, 7.7, 19.0, 7.0, title, value, note, color)

    ax.plot([18.8, 21.3], [13.5, 10.0], color=PAPER["red"], lw=1.1, zorder=6)
    ax.plot([18.8, 21.3], [13.5, 10.0], "o", ms=2.2, color=PAPER["red"], zorder=7)
    ax.plot([42.6, 45.0, 47.4], [13.8, 11.5, 10.2], color=PAPER["blue_dark"], lw=1.1, zorder=6)
    ax.plot([42.6, 45.0, 47.4], [13.8, 11.5, 10.2], "o", ms=2.1, color=PAPER["blue_dark"], zorder=7)
    ax.axhline(11.6, xmin=0.615, xmax=0.685, color="#999999", lw=0.65, ls=":", zorder=5)
    ax.plot([63.4, 66.0, 68.4], [12.1, 13.6, 12.8], "o", ms=2.4, color=PAPER["orange"], zorder=7)
    ax.add_patch(Rectangle((88.9, 9.8), 1.2, 4.2, facecolor="#7A4CC2", edgecolor="#333333", lw=0.45, zorder=7))
    ax.add_patch(Rectangle((91.0, 9.8), 1.2, 0.7, facecolor="#D8CFF0", edgecolor="#333333", lw=0.35, zorder=7))

    fig.tight_layout(pad=0.12)
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
    df = df.sort_values("overall_ko", ascending=True).reset_index(drop=True)
    general = {"Phi-3.5", "Mistral-7B", "Llama-8B", "Gemma-9B"}
    fig, ax = plt.subplots(figsize=(6.25, 3.55))
    ax.set_title("Qwen-32B single-grade score shift from English to Korean", loc="left", fontsize=8.8, fontweight="bold")
    ax.set_xlim(-0.18, 1.55)
    ax.set_ylim(4.35, 8.65)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["English", "Korean"])
    ax.set_ylabel("MT-Bench score (1-10)")
    ax.grid(axis="y", color="#E5E5E5", lw=0.6, linestyle="--", alpha=0.9)
    ax.set_axisbelow(True)
    ax.spines["bottom"].set_visible(False)

    for idx, row in enumerate(df.itertuples(index=False)):
        color = PAPER["red"] if row.label in general else PAPER["blue_dark"]
        ax.plot([0, 1], [row.overall_en, row.overall_ko], color=color, lw=1.35, alpha=0.92, zorder=2)
        ax.plot(0, row.overall_en, "o", ms=4.2, mfc="white", mec=color, mew=1.1, zorder=3)
        ax.plot(1, row.overall_ko, "o", ms=4.2, mfc=color, mec=color, mew=0.8, zorder=3)
        label_y = row.overall_ko
        if row.label == "Phi-3.5":
            label_y += 0.07
        if row.label == "Mistral-7B":
            label_y -= 0.06
        ax.text(
            1.04,
            label_y,
            f"{row.label} ({row.gap:+.2f})",
            ha="left",
            va="center",
            fontsize=6.3,
            color=color,
            zorder=5,
        )

    ax.text(0, 8.52, "English score", ha="center", va="bottom", fontsize=6.2, color="#555555")
    ax.text(1, 8.52, "Korean score", ha="center", va="bottom", fontsize=6.2, color="#555555")
    legend_handles = [
        Line2D([0], [0], color=PAPER["red"], lw=1.5, label="general-purpose LLM"),
        Line2D([0], [0], color=PAPER["blue_dark"], lw=1.5, label="Korean-adapted LLM"),
    ]
    ax.legend(handles=legend_handles, frameon=False, loc="lower left", bbox_to_anchor=(0.00, -0.02), handlelength=1.4)
    ax.text(0.0, -0.18, "Right-side annotations report Korean minus English score.", transform=ax.transAxes, fontsize=6.5, color="#555555")
    ax.spines["left"].set_color("#555555")
    save(fig, "fig2_score_gap_qwen32")


def fig3_reliability_bias() -> None:
    comp = read_csv(ROOT / "data/ko/results/results_en_ko_comparison.csv")
    comp["judge_label"] = comp["judge"].map(JUDGE_LABELS)
    comp["en_fp_in_incon"] = comp["en_fp_pct"] / comp["en_incon_pct"] * 100
    comp["ko_fp_in_incon"] = comp["ko_fp_pct"] / comp["ko_incon_pct"] * 100
    en_color = PAPER["blue_dark"]
    ko_color = PAPER["red"]
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.20))

    qwen = comp[comp["judge"].isin(["qwen_7B", "qwen_14B", "qwen_32B"])].copy()
    qwen["size_b"] = qwen["judge"].map({"qwen_7B": 7, "qwen_14B": 14, "qwen_32B": 32})
    qwen = qwen.sort_values("size_b")

    ax = axes[0]
    ax.plot(qwen["size_b"], qwen["en_incon_pct"], "-o", color=en_color, mfc="white", mec=en_color, mew=1.2, lw=1.5, label="EN")
    ax.plot(qwen["size_b"], qwen["ko_incon_pct"], "-s", color=ko_color, mfc=ko_color, mec="#222222", mew=0.5, lw=1.5, label="KO")
    for x, yv in zip(qwen["size_b"], qwen["en_incon_pct"]):
        ax.text(x, yv + 2.4, f"{yv:.1f}", ha="center", va="bottom", fontsize=6.0, color=en_color)
    for x, yv in zip(qwen["size_b"], qwen["ko_incon_pct"]):
        ax.text(x, yv - 3.0, f"{yv:.1f}", ha="center", va="top", fontsize=6.0, color=ko_color)
    ax.set_title("(a) Same-family judge scaling", loc="left", fontsize=8.5, fontweight="bold")
    ax.set_xlabel("Judge size")
    ax.set_ylabel("AB/BA inconsistency (%)")
    ax.set_xticks([7, 14, 32])
    ax.set_xticklabels(["7B", "14B", "32B"])
    ax.set_ylim(0, 86)
    ax.grid(axis="y", color="#E1E1E1", lw=0.60, linestyle="--", alpha=0.85)
    ax.legend(frameon=False, loc="upper right", ncol=2, handletextpad=0.35, columnspacing=0.8)

    ax = axes[1]
    order = ["Qwen-7B", "Qwen-14B", "Qwen-32B", "EXAONE-32B", "GPT-4o-mini"]
    comp_pos = comp.set_index("judge_label").loc[order].reset_index()
    ax.axhline(50, color="#777777", lw=0.8, ls=":")
    ax.text(82.5, 51.5, "no first-position preference", ha="right", va="bottom", fontsize=5.8, color="#555555")
    label_offsets = {
        "Qwen-7B": (1.0, 1.8),
        "Qwen-14B": (1.0, -3.8),
        "Qwen-32B": (1.0, -4.2),
        "EXAONE-32B": (-7.4, 3.0),
        "GPT-4o-mini": (-14.0, -5.0),
    }
    for row in comp_pos.itertuples(index=False):
        judge_name = row.judge_label
        family_color = PAPER["blue_dark"] if judge_name.startswith("Qwen") else PAPER["orange"]
        en_xy = (row.en_incon_pct, row.en_fp_in_incon)
        ko_xy = (row.ko_incon_pct, row.ko_fp_in_incon)
        ax.plot([en_xy[0], ko_xy[0]], [en_xy[1], ko_xy[1]], color="#B4BBC3", lw=1.0, zorder=1)
        ax.plot(en_xy[0], en_xy[1], "o", ms=4.6, mfc="white", mec=family_color, mew=1.15, zorder=3)
        ax.plot(ko_xy[0], ko_xy[1], "s", ms=4.3, mfc=family_color, mec="#222222", mew=0.45, zorder=3)
        mx = (en_xy[0] + ko_xy[0]) / 2
        my = (en_xy[1] + ko_xy[1]) / 2
        dx, dy = label_offsets[judge_name]
        ax.text(mx + dx, my + dy, judge_name, ha="left", va="center", fontsize=5.6, color=family_color, fontweight="bold")
    ax.set_title("(b) Instability-bias map", loc="left", fontsize=8.5, fontweight="bold")
    ax.set_xlabel("AB/BA inconsistency (%)")
    ax.set_ylabel("First-position share (%)", fontsize=7.0, labelpad=2)
    ax.set_xlim(15, 84)
    ax.set_ylim(18, 96)
    ax.grid(color="#E1E1E1", lw=0.60, linestyle="--", alpha=0.85)
    handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor="white", markeredgecolor="#444444", markeredgewidth=1.1, markersize=4.8, label="EN"),
        Line2D([0], [0], marker="s", color="none", markerfacecolor="#444444", markeredgecolor="#222222", markersize=4.6, label="KO"),
        Line2D([0], [0], color=PAPER["blue_dark"], lw=1.4, label="Qwen same-family"),
        Line2D([0], [0], color=PAPER["orange"], lw=1.4, label="cross-family"),
    ]
    ax.legend(handles=handles, frameon=False, loc="lower right", fontsize=5.9, handletextpad=0.35, borderpad=0.2)
    for ax in axes:
        ax.spines["left"].set_color("#555555")
        ax.spines["bottom"].set_color("#555555")
        ax.set_axisbelow(True)
    fig.text(0.52, -0.01, "Panel (b) reports first-position share only among AB/BA disagreements.", ha="center", fontsize=6.5, color="#555555")
    fig.tight_layout(w_pad=3.0)
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


def judge_family(judge: str) -> str:
    return "same-family" if judge.startswith("Qwen") else "cross-family"


def gap_band(gap: float) -> str:
    if gap <= -1.5:
        return "large"
    if gap <= -0.5:
        return "moderate"
    return "small"


def model_group(label: str) -> str:
    return "Korean-adapted" if label in {"EXAONE-7.8B", "EEVE-10.8B"} else "general-purpose"


def fmt_pct(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}%"


def fmt_tex_pct(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}\\%"


def latex_table(caption: str, label: str, headers: list[str], rows: list[list[str]], align: str) -> str:
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        rf"\caption{{{caption}}}",
        rf"\label{{{label}}}",
        r"\small",
        rf"\begin{{tabular}}{{{align}}}",
        r"\toprule",
        " & ".join(headers) + r" \\",
        r"\midrule",
    ]
    for row in rows:
        lines.append(" & ".join(row) + r" \\")
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}", ""])
    return "\n".join(lines)


def fig4_ref_parse() -> None:
    ref = collect_ref_score_diff()
    ref_parse = reference_parse_summary()

    judge_order = ["Qwen-7B", "Qwen-14B", "Qwen-32B", "EXAONE-32B", "GPT-4o-mini"]
    judge_short = ["Qwen-7B", "Qwen-14B", "Qwen-32B", "EXAONE-32B", "GPT-4o-mini"]

    ref_lookup = {(r.lang, r.judge): r.diff_ref_minus_nonref for r in ref.itertuples(index=False)}
    parse_lookup = {(r.lang, r.judge): r.failure_rate * 100 for r in ref_parse.itertuples(index=False)}
    en_ref = np.array([ref_lookup[("EN", j)] for j in judge_order])
    ko_ref = np.array([ref_lookup[("KO", j)] for j in judge_order])
    en_parse = np.array([parse_lookup[("EN", j)] for j in judge_order])
    ko_parse = np.array([parse_lookup[("KO", j)] for j in judge_order])

    ref_matrix = np.vstack([en_ref, ko_ref])
    parse_matrix = np.vstack([en_parse, ko_parse])

    fig, axes = plt.subplots(1, 2, figsize=(8.25, 2.55))

    heatmaps = [
        (axes[0], -ref_matrix, ref_matrix, "(a) Reference-guided score drop", "Score-drop magnitude", 0, 2.6, "{:+.2f}"),
        (axes[1], parse_matrix, parse_matrix, "(b) Reference parse failure", "Failure rate (%)", 0, 35, "{:.1f}"),
    ]
    for ax, color_values, text_values, title, cbar_label, vmin, vmax, fmt in heatmaps:
        im = ax.imshow(color_values, cmap="OrRd", vmin=vmin, vmax=vmax, aspect="auto")
        ax.set_title(title, loc="left", fontsize=8.5, fontweight="bold")
        ax.set_xticks(np.arange(len(judge_short)))
        ax.set_xticklabels(judge_short, rotation=25, ha="right")
        ax.set_yticks([0, 1])
        ax.set_yticklabels(["EN", "KO"])
        for i in range(text_values.shape[0]):
            for j in range(text_values.shape[1]):
                raw = text_values[i, j]
                intensity = color_values[i, j]
                color = "white" if intensity > (vmax * 0.55) else "#111111"
                ax.text(j, i, fmt.format(raw), ha="center", va="center", fontsize=6.2, fontweight="bold", color=color)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_xticks(np.arange(-0.5, len(judge_short), 1), minor=True)
        ax.set_yticks(np.arange(-0.5, 2, 1), minor=True)
        ax.grid(which="minor", color="white", linewidth=1.2)
        ax.tick_params(which="minor", bottom=False, left=False)
        cbar = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.025)
        cbar.ax.tick_params(labelsize=6.0, length=2)
        cbar.set_label(cbar_label, fontsize=6.2)
    fig.text(0.52, -0.02, "Darker cells indicate larger score drop or higher parse-failure rate.", ha="center", fontsize=6.8, color="#555555")
    fig.tight_layout(w_pad=2.0)
    save(fig, "fig4_ref_parse_failure")


def write_tables() -> None:
    gap = qwen32_gap_frame().copy()
    gap["Model"] = gap["label"]
    gap["Group"] = gap["label"].map(model_group)
    gap["EN"] = gap["overall_en"].map(lambda x: f"{x:.2f}")
    gap["KO"] = gap["overall_ko"].map(lambda x: f"{x:.2f}")
    gap["KO-EN"] = gap["gap"].map(lambda x: f"{x:+.2f}")
    gap["Drop size"] = gap["gap"].map(gap_band)

    comp = read_csv(ROOT / "data/ko/results/results_en_ko_comparison.csv").copy()
    comp["Judge"] = comp["judge"].map(JUDGE_LABELS)
    comp["Family"] = comp["Judge"].map(judge_family)
    comp["EN inconsistency"] = comp["en_incon_pct"].map(lambda x: f"{x:.1f}%")
    comp["KO inconsistency"] = comp["ko_incon_pct"].map(lambda x: f"{x:.1f}%")
    comp["EN first-pos/incon"] = (comp["en_fp_pct"] / comp["en_incon_pct"] * 100).map(lambda x: f"{x:.0f}%")
    comp["KO first-pos/incon"] = (comp["ko_fp_pct"] / comp["ko_incon_pct"] * 100).map(lambda x: f"{x:.0f}%")

    ref = collect_ref_score_diff().copy()
    ref_lookup = {(row.lang, row.judge): row for row in ref.itertuples(index=False)}

    ref_parse = reference_parse_summary().copy()
    parse_lookup = {(row.lang, row.judge): row.failure_rate * 100 for row in ref_parse.itertuples(index=False)}

    judge_order = ["Qwen-7B", "Qwen-14B", "Qwen-32B", "EXAONE-32B", "GPT-4o-mini"]
    setup_rows = [
        {
            "구성 요소": "Benchmark",
            "규모": f"{question_count()} two-turn items x 2 languages",
            "논문상 역할": "원 MT-Bench와 한국어 번역본을 같은 문항 단위로 직접 비교",
        },
        {
            "구성 요소": "Answer generation",
            "규모": f"{len(MODEL_LABELS)} evaluated LLMs x EN/KO",
            "논문상 역할": "모델군별 한국어 점수 하락과 한국어 적응 모델의 완충 효과 확인",
        },
        {
            "구성 요소": "Judge settings",
            "규모": f"{len(JUDGE_LABELS)} judges",
            "논문상 역할": "same-family Qwen judge와 cross-family judge의 판정 편향 비교",
        },
        {
            "구성 요소": "Judgment modes",
            "규모": "single / pairwise AB-BA / reference",
            "논문상 역할": "점수 차이, 순서 민감도, reference 제공 효과를 분리 측정",
        },
        {
            "구성 요소": "Audit records",
            "규모": f"{raw_judgment_file_count()} raw judgment JSONL files",
            "논문상 역할": "집계표뿐 아니라 원시 판정 파일에서 결과 재계산 가능",
        },
    ]

    reliability_rows = []
    reference_rows = []
    reference_detail_rows = []
    for judge in judge_order:
        comp_row = comp[comp["Judge"] == judge].iloc[0]
        reliability_rows.append(
            {
                "Judge": judge,
                "Family": judge_family(judge),
                "EN inc.": fmt_pct(float(comp_row.en_incon_pct)),
                "KO inc.": fmt_pct(float(comp_row.ko_incon_pct)),
                "EN first": f"{float(comp_row.en_fp_pct / comp_row.en_incon_pct * 100):.0f}%",
                "KO first": f"{float(comp_row.ko_fp_pct / comp_row.ko_incon_pct * 100):.0f}%",
                "EN ref parse": fmt_pct(parse_lookup[("EN", judge)]),
                "KO ref parse": fmt_pct(parse_lookup[("KO", judge)]),
            }
        )

        en = ref_lookup[("EN", judge)]
        ko = ref_lookup[("KO", judge)]
        reference_rows.append(
            {
                "Judge": judge,
                "EN drop": f"{float(en.diff_ref_minus_nonref):+.2f}",
                "KO drop": f"{float(ko.diff_ref_minus_nonref):+.2f}",
                "EN parse": fmt_pct(parse_lookup[("EN", judge)]),
                "KO parse": fmt_pct(parse_lookup[("KO", judge)]),
            }
        )
        reference_detail_rows.append(
            {
                "Judge": judge,
                "EN non-ref": f"{float(en.nonref_mean):.2f}",
                "EN ref": f"{float(en.ref_mean):.2f}",
                "EN drop": f"{float(en.diff_ref_minus_nonref):+.2f}",
                "KO non-ref": f"{float(ko.nonref_mean):.2f}",
                "KO ref": f"{float(ko.ref_mean):.2f}",
                "KO drop": f"{float(ko.diff_ref_minus_nonref):+.2f}",
                "EN parse": fmt_pct(parse_lookup[("EN", judge)]),
                "KO parse": fmt_pct(parse_lookup[("KO", judge)]),
            }
        )

    setup = pd.DataFrame(setup_rows)
    reliability = pd.DataFrame(reliability_rows)
    reference = pd.DataFrame(reference_rows)

    content = "# Paper-ready Tables\n\n"
    content += "## Table 1. Experimental design for the Korean MT-Bench reliability audit\n\n"
    content += setup.to_markdown(index=False, disable_numparse=True)
    content += "\n\n## Table 2. Qwen-32B judge score shift from English to Korean\n\n"
    content += gap[["Model", "Group", "EN", "KO", "KO-EN", "Drop size"]].to_markdown(index=False, disable_numparse=True)
    content += "\n\n## Table 3. Pairwise judge reliability and first-position tendency\n\n"
    content += reliability.to_markdown(index=False, disable_numparse=True)
    content += "\n\n## Table 4. Reference-guided score penalty and parse failure\n\n"
    content += reference.to_markdown(index=False, disable_numparse=True)
    content += "\n\n## Appendix Table A1. Detailed reference-guided score means\n\n"
    content += pd.DataFrame(reference_detail_rows).to_markdown(index=False, disable_numparse=True)
    content += "\n"

    path = TABLE_OUT / "kci_tables.md"
    path.write_text(content, encoding="utf-8")
    print(f"saved {path.relative_to(ROOT)}")

    setup_tex_rows = [[row["구성 요소"], row["규모"], row["논문상 역할"]] for _, row in setup.iterrows()]
    gap_tex_rows = [
        [row["Model"], row["Group"], row["EN"], row["KO"], row["KO-EN"], row["Drop size"]]
        for _, row in gap[["Model", "Group", "EN", "KO", "KO-EN", "Drop size"]].iterrows()
    ]
    reliability_tex_rows = []
    for judge in judge_order:
        comp_row = comp[comp["Judge"] == judge].iloc[0]
        reliability_tex_rows.append(
            [
                judge,
                judge_family(judge),
                fmt_tex_pct(float(comp_row.en_incon_pct)),
                fmt_tex_pct(float(comp_row.ko_incon_pct)),
                f"{float(comp_row.en_fp_pct / comp_row.en_incon_pct * 100):.0f}\\%",
                f"{float(comp_row.ko_fp_pct / comp_row.ko_incon_pct * 100):.0f}\\%",
                fmt_tex_pct(parse_lookup[("EN", judge)]),
                fmt_tex_pct(parse_lookup[("KO", judge)]),
            ]
        )
    reference_tex_rows = []
    for judge in judge_order:
        en = ref_lookup[("EN", judge)]
        ko = ref_lookup[("KO", judge)]
        reference_tex_rows.append(
            [
                judge,
                f"{float(en.diff_ref_minus_nonref):+.2f}",
                f"{float(ko.diff_ref_minus_nonref):+.2f}",
                fmt_tex_pct(parse_lookup[("EN", judge)]),
                fmt_tex_pct(parse_lookup[("KO", judge)]),
            ]
        )

    tex = "% Requires \\usepackage{booktabs}\n\n"
    tex += latex_table(
        "한국어 MT-Bench 신뢰도 분석을 위한 실험 구성.",
        "tab:experimental-design",
        ["구성 요소", "규모", "논문상 역할"],
        setup_tex_rows,
        "llp{7.2cm}",
    )
    tex += latex_table(
        "Qwen-32B judge 기준 영어-한국어 single-grade 점수 변화.",
        "tab:qwen32-score-gap",
        ["Model", "Group", "EN", "KO", "KO-EN", "Drop"],
        gap_tex_rows,
        "llrrrr",
    )
    tex += latex_table(
        "Pairwise judge reliability와 first-position tendency.",
        "tab:judge-reliability",
        ["Judge", "Family", "EN Inc.", "KO Inc.", "EN First", "KO First", "EN Parse", "KO Parse"],
        reliability_tex_rows,
        "llrrrrrr",
    )
    tex += latex_table(
        "Reference-guided scoring에서의 점수 penalty와 parse failure.",
        "tab:reference-score-change",
        ["Judge", "EN Drop", "KO Drop", "EN Parse", "KO Parse"],
        reference_tex_rows,
        "lrrrr",
    )
    tex_path = TABLE_OUT / "kci_tables.tex"
    tex_path.write_text(tex, encoding="utf-8")
    print(f"saved {tex_path.relative_to(ROOT)}")


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
    print(f"Generating paper-ready figures under {FIG_OUT.relative_to(ROOT)}/")
    fig1_protocol()
    fig2_score_gap()
    fig3_reliability_bias()
    fig4_ref_parse()
    write_tables()
    print_audit()


if __name__ == "__main__":
    main()
