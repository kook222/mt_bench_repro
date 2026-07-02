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
from textwrap import dedent

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, Rectangle


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


def workflow_arrow(ax: plt.Axes, x1: float, y1: float, x2: float, y2: float) -> None:
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1),
            (x2, y2),
            arrowstyle="-|>",
            mutation_scale=9,
            linewidth=0.85,
            color="#222222",
            zorder=5,
        )
    )


def workflow_column(
    ax: plt.Axes,
    x: float,
    y: float,
    w: float,
    h: float,
    number: str,
    title: str,
    rows: list[tuple[str, str]],
) -> None:
    ax.add_patch(Rectangle((x, y), w, h, facecolor="white", edgecolor="#222222", linewidth=0.9))
    ax.add_patch(Rectangle((x, y + h - 0.58), w, 0.58, facecolor="#E9EDF2", edgecolor="#222222", linewidth=0.9))
    ax.text(x + 0.18, y + h - 0.29, number, ha="left", va="center", fontsize=7.3, fontweight="bold")
    ax.text(x + w / 2 + 0.12, y + h - 0.29, title, ha="center", va="center", fontsize=7.6, fontweight="bold")

    row_h = (h - 0.9) / len(rows)
    top = y + h - 0.82
    for idx, (tag, text) in enumerate(rows):
        yy = top - (idx + 1) * row_h
        ax.add_patch(Rectangle((x + 0.15, yy + 0.08), 0.62, row_h - 0.16, facecolor="#F4F4F4", edgecolor="#777777", linewidth=0.55))
        ax.text(x + 0.46, yy + row_h / 2, tag, ha="center", va="center", fontsize=5.9, fontweight="bold")
        ax.text(x + 0.92, yy + row_h / 2, text, ha="left", va="center", fontsize=6.55, linespacing=1.1)


def fig1_protocol() -> None:
    fig, ax = plt.subplots(figsize=(7.6, 3.55))
    ax.set_axis_off()
    ax.set_xlim(0, 10.2)
    ax.set_ylim(0, 5.6)

    ax.text(0.08, 5.35, "Experimental workflow for Korean MT-Bench reliability analysis", ha="left", va="center", fontsize=9.2, fontweight="bold")
    ax.plot([0.08, 10.02], [5.12, 5.12], color="#222222", lw=0.75)

    columns = [
        (
            "1",
            "Benchmark",
            [
                ("Q", "MT-Bench\n80 English items"),
                ("KO", "manual Korean\ntranslation"),
                ("BT", "back-translation\nvalidity check"),
            ],
        ),
        (
            "2",
            "Answer Set",
            [
                ("M", "6 evaluated LLMs"),
                ("L", "English and Korean\nresponses"),
                ("P", "paired by\nitem and model"),
            ],
        ),
        (
            "3",
            "Judge Matrix",
            [
                ("J", "5 judge settings\nQwen/EXAONE/GPT"),
                ("R", "single, pairwise,\nreference-guided"),
                ("O", "AB and BA order\nraw JSONL records"),
            ],
        ),
        (
            "4",
            "Reliability Audit",
            [
                ("S", "score gap"),
                ("I", "order-swap\ninconsistency"),
                ("B", "position tendency\nparse failure"),
            ],
        ),
    ]
    x0, w, gap, y, h = 0.18, 2.15, 0.35, 1.0, 3.82
    for idx, (number, title, rows) in enumerate(columns):
        x = x0 + idx * (w + gap)
        workflow_column(ax, x, y, w, h, number, title, rows)
        if idx < len(columns) - 1:
            workflow_arrow(ax, x + w + 0.05, y + h / 2, x + w + gap - 0.05, y + h / 2)

    ax.add_patch(Rectangle((0.18, 0.28), 9.65, 0.42, facecolor="#F7F7F7", edgecolor="#777777", linewidth=0.55))
    ax.text(5.0, 0.49, "Recomputation path: raw JSONL judgments -> aggregate CSV tables -> paper figures", ha="center", va="center", fontsize=6.7, color="#333333")

    fig.tight_layout(pad=0.2)
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
    df = df.sort_values("gap", ascending=True).reset_index(drop=True)
    y = np.arange(len(df))

    fig, ax = plt.subplots(figsize=(6.8, 3.15))
    for idx, row in enumerate(df.itertuples(index=False)):
        ax.hlines(idx, row.overall_ko, row.overall_en, color="#9EA7B3", lw=1.6, zorder=1)
        ax.plot(row.overall_en, idx, "o", ms=4.8, mfc="white", mec="#222222", mew=1.0, zorder=4)
        ax.plot(row.overall_ko, idx, "s", ms=4.5, mfc="#222222", mec="#222222", mew=0.8, zorder=4)
        ax.text(
            8.66,
            idx,
            f"{row.gap:+.2f}",
            ha="center",
            va="center",
            fontsize=7.0,
            color="#222222",
            zorder=5,
        )
    ax.set_yticks(y)
    ax.set_yticklabels(df["label"])
    ax.set_xlabel("MT-Bench score (1-10)")
    ax.set_xlim(4.2, 8.9)
    ax.set_title("Qwen-32B judge: English vs. Korean single-grade scores", loc="left", fontsize=8.8, fontweight="bold")
    ax.grid(axis="x", color="#E1E1E1", lw=0.55)
    ax.set_axisbelow(True)
    ax.text(8.66, len(df) - 0.15, "KO-EN", ha="center", va="bottom", fontsize=7.0, color="#333333")
    legend_handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor="white", markeredgecolor="#222222", markeredgewidth=1.0, markersize=5, label="EN"),
        Line2D([0], [0], marker="s", color="none", markerfacecolor="#222222", markeredgecolor="#222222", markersize=5, label="KO"),
    ]
    ax.legend(handles=legend_handles, frameon=False, loc="upper left", bbox_to_anchor=(0.02, 0.98), ncol=2, handletextpad=0.35, columnspacing=0.85)
    ax.text(0.0, -0.20, "Values at right report Korean minus English score.", transform=ax.transAxes, fontsize=6.8, color="#555555")
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_color("#555555")
    save(fig, "fig2_score_gap_qwen32")


def fig3_reliability_bias() -> None:
    comp = read_csv(ROOT / "data/ko/results/results_en_ko_comparison.csv")
    comp["judge_label"] = comp["judge"].map(JUDGE_LABELS)
    comp["en_fp_in_incon"] = comp["en_fp_pct"] / comp["en_incon_pct"] * 100
    comp["ko_fp_in_incon"] = comp["ko_fp_pct"] / comp["ko_incon_pct"] * 100
    y = np.arange(len(comp))
    height = 0.34
    fig, axes = plt.subplots(1, 2, figsize=(7.7, 3.05), sharey=True)

    panels = [
        (axes[0], "AB/BA inconsistency (%)", "en_incon_pct", "ko_incon_pct", "(a) Order-swap inconsistency", (0, 86), "{:.1f}"),
        (axes[1], "First-position share within inconsistent pairs (%)", "en_fp_in_incon", "ko_fp_in_incon", "(b) First-position tendency", (0, 102), "{:.0f}"),
    ]
    for ax, xlabel, en_col, ko_col, title, xlim, fmt in panels:
        ax.barh(y - height / 2, comp[en_col], height, facecolor="white", edgecolor="#222222", linewidth=0.8, label="EN")
        ax.barh(y + height / 2, comp[ko_col], height, facecolor="#555555", edgecolor="#222222", linewidth=0.8, label="KO")
        for yi, value in zip(y - height / 2, comp[en_col]):
            ax.text(value + 1.0, yi, fmt.format(value), ha="left", va="center", fontsize=5.9, color="#222222")
        for yi, value in zip(y + height / 2, comp[ko_col]):
            ax.text(value + 1.0, yi, fmt.format(value), ha="left", va="center", fontsize=5.9, color="#222222")
        ax.set_title(title, loc="left", fontsize=8.4, fontweight="bold")
        ax.set_xlabel(xlabel)
        ax.set_xlim(*xlim)
        ax.set_yticks(y)
        ax.set_yticklabels(comp["judge_label"])
        ax.grid(axis="x", color="#E1E1E1", lw=0.55)
        ax.set_axisbelow(True)
        ax.spines["left"].set_color("#555555")
        ax.spines["bottom"].set_color("#555555")

    axes[0].invert_yaxis()
    axes[1].axvline(50, color="#777777", lw=0.8, ls=":")
    axes[1].text(50.8, -0.58, "chance", ha="left", va="center", fontsize=6.2, color="#555555")
    axes[0].legend(frameon=False, loc="lower right", ncol=2, handletextpad=0.35, columnspacing=0.8)
    fig.text(0.52, -0.01, "Panel (b) conditions on the subset where AB and BA judgments disagree.", ha="center", fontsize=6.8, color="#555555")
    fig.tight_layout(w_pad=1.6)
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
    judge_short = ["Qwen-7B", "Qwen-14B", "Qwen-32B", "EXAONE-32B", "GPT-4o-mini"]
    y = np.arange(len(judge_order))
    height = 0.34

    ref_lookup = {(r.lang, r.judge): r.diff_ref_minus_nonref for r in ref.itertuples(index=False)}
    parse_lookup = {(r.lang, r.judge): r.failure_rate * 100 for r in ref_parse.itertuples(index=False)}
    en_ref = np.array([ref_lookup[("EN", j)] for j in judge_order])
    ko_ref = np.array([ref_lookup[("KO", j)] for j in judge_order])
    en_parse = np.array([parse_lookup[("EN", j)] for j in judge_order])
    ko_parse = np.array([parse_lookup[("KO", j)] for j in judge_order])

    fig, axes = plt.subplots(1, 2, figsize=(8.1, 3.05), sharey=True)

    ax = axes[0]
    ax.barh(y - height / 2, en_ref, height, color="white", edgecolor="#222222", linewidth=0.8, label="EN")
    ax.barh(y + height / 2, ko_ref, height, color="#555555", edgecolor="#222222", linewidth=0.8, label="KO")
    ax.axvline(0, color="#222222", lw=0.8)
    ax.set_title("(a) Reference-guided score change", loc="left", fontsize=8.4, fontweight="bold")
    ax.set_xlabel("Ref - non-ref score")
    ax.set_xlim(-2.8, 0.25)
    ax.set_yticks(y)
    ax.set_yticklabels(judge_short)
    ax.grid(axis="x", color="#E1E1E1", lw=0.55)
    ax.set_axisbelow(True)
    for yi, val in zip(y - height / 2, en_ref):
        ax.text(val - 0.06, yi, f"{val:.2f}", ha="right", va="center", fontsize=5.9)
    for yi, val in zip(y + height / 2, ko_ref):
        ax.text(val - 0.06, yi, f"{val:.2f}", ha="right", va="center", fontsize=5.9)

    ax = axes[1]
    ax.barh(y - height / 2, en_parse, height, color="white", edgecolor="#222222", linewidth=0.8, label="EN")
    ax.barh(y + height / 2, ko_parse, height, color="#555555", edgecolor="#222222", linewidth=0.8, label="KO")
    ax.set_title("(b) Reference parse failure", loc="left", fontsize=8.4, fontweight="bold")
    ax.set_xlabel("Failure rate (%)")
    ax.set_xlim(0, 36)
    ax.set_yticks(y)
    ax.set_yticklabels(judge_short)
    ax.grid(axis="x", color="#E1E1E1", lw=0.55)
    ax.set_axisbelow(True)
    for yi, val in zip(y - height / 2, en_parse):
        ax.text(max(val + 0.7, 0.7), yi, f"{val:.1f}", ha="left", va="center", fontsize=5.9)
    for yi, val in zip(y + height / 2, ko_parse):
        ax.text(max(val + 0.7, 0.7), yi, f"{val:.1f}", ha="left", va="center", fontsize=5.9)
    axes[0].invert_yaxis()
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, loc="lower center", bbox_to_anchor=(0.50, -0.03), ncol=2, handletextpad=0.35, columnspacing=1.0)
    for ax in axes:
        ax.spines["left"].set_color("#555555")
        ax.spines["bottom"].set_color("#555555")
    fig.tight_layout(w_pad=1.6)
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

    content = "# KCI-ready Copy Tables\n\n"
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
        # Paper Artifacts

        이 도표 세트는 국내 학회/학술지 투고 원고에 맞춰 본문 삽입용으로 설계했다.
        색 의존도를 줄이고, 흑백 인쇄에서도 구분되도록 grayscale bar, marker shape, direct label을 사용한다.

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
        3. **Fig. 3. Pairwise inconsistency and first-position tendency.**
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
    print(f"Generating paper-ready figures under {FIG_OUT.relative_to(ROOT)}/")
    fig1_protocol()
    fig2_score_gap()
    fig3_reliability_bias()
    fig4_ref_parse()
    write_tables()
    write_notes()
    print_audit()


if __name__ == "__main__":
    main()
