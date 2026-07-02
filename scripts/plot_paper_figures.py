#!/usr/bin/env python3
"""
scripts/plot_paper_figures.py

Publication figures for Korean MT-Bench paper (KIPS format).
Figure sizes follow KIPS 2-column A4 layout:
  - Single column : ~82 mm = 3.23"
  - Full width    : ~170 mm = 6.69"

Usage:
    cd mt_bench_repro
    python scripts/plot_paper_figures.py

Output:
    figures/paper/fig1_inconsistency_rate.{png,pdf}
    figures/paper/fig2_position_bias_breakdown.{png,pdf}
    figures/paper/fig3_en_ko_score_scatter.{png,pdf}
    figures/paper/fig4_category_gap.{png,pdf}
"""

from __future__ import annotations

import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from io import StringIO
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT    = Path(__file__).resolve().parents[1]   # mt_bench_repro/
DATA_EN = ROOT / "data" / "en" / "results"
DATA_KO = ROOT / "data" / "ko" / "results"
OUT     = ROOT / "figures" / "paper"

# ── KIPS column widths (inches) ───────────────────────────────────────────────
W_FULL  = 6.69   # 170 mm — spans both columns
W_HALF  = 3.23   # 82 mm  — single column

# ── Color palette (Okabe-Ito colorblind-friendly) ─────────────────────────────
C_EN    = "#0072B2"   # blue        – English / general-purpose
C_KO    = "#D55E00"   # vermillion  – Korean / Korean-specialized
C_FP    = "#D55E00"   # 1st-pos bias
C_SP    = "#E69F00"   # 2nd-pos bias (amber)
C_MIX   = "#BBBBBB"   # tie / mix   (light gray)
C_BAR   = "#4878CF"   # neutral bar (Fig 4)

# ── Judge / model constants ────────────────────────────────────────────────────
QWEN_JUDGES  = ["qwen_7B", "qwen_14B", "qwen_32B"]
CROSS_JUDGES = ["exaone_32B", "gpt4omini"]
ALL_JUDGES   = QWEN_JUDGES + CROSS_JUDGES

JUDGE_DISPLAY = {
    "qwen_7B":    "Qwen-7B",
    "qwen_14B":   "Qwen-14B",
    "qwen_32B":   "Qwen-32B",
    "exaone_32B": "EXAONE-32B",
    "gpt4omini":  "GPT-4o-mini",
}

PAIRWISE_DIRS = {
    "qwen_7B":    ("qwen/judge_7B",         "qwen/judge_7B"),
    "qwen_14B":   ("qwen/judge_14B",        "qwen/judge_14B"),
    "qwen_32B":   ("qwen/judge_32B",        "qwen/judge_32B"),
    "exaone_32B": ("exaone/judge_32B",      "exaone/judge_32B"),
    "gpt4omini":  ("gpt/judge_gpt4omini",   "gpt/judge_gpt4omini"),
}

MODEL_SHORT = {
    "EEVE-Korean-Instruct-10.8B": "EEVE-10.8B",
    "EXAONE-3.5-7.8B-Instruct":   "EXAONE-7.8B",
    "Llama-3.1-8B-Instruct":      "Llama-3.1-8B",
    "Mistral-7B-Instruct-v0.3":   "Mistral-7B",
    "Phi-3.5-mini-Instruct":      "Phi-3.5-mini",
    "gemma-2-9b-it":              "Gemma-2-9B",
}
KO_SPEC = {"EEVE-Korean-Instruct-10.8B", "EXAONE-3.5-7.8B-Instruct"}

CAT_DISPLAY = {
    "writing":    "Writing",
    "roleplay":   "Roleplay",
    "reasoning":  "Reasoning",
    "math":       "Math",
    "coding":     "Coding",
    "extraction": "Extraction",
    "stem":       "STEM",
    "humanities": "Humanities",
}


# ═════════════════════════════════════════════════════════════════════════════
# Common helpers
# ═════════════════════════════════════════════════════════════════════════════

def set_paper_style() -> None:
    """Global rcParams sized for KIPS single-column figures (82 mm)."""
    plt.rcParams.update({
        "font.family":         "DejaVu Sans",
        "font.size":           8,
        "axes.labelsize":      8,
        "axes.titlesize":      8,
        "xtick.labelsize":     7,
        "ytick.labelsize":     7,
        "legend.fontsize":     7,
        "legend.framealpha":   0.95,
        "legend.edgecolor":    "#DDDDDD",
        "legend.borderpad":    0.4,
        "legend.handlelength": 1.2,
        "legend.handleheight": 0.7,
        "axes.spines.top":     False,
        "axes.spines.right":   False,
        "axes.linewidth":      0.6,
        "xtick.major.width":   0.6,
        "ytick.major.width":   0.6,
        "xtick.major.size":    2.5,
        "ytick.major.size":    2.5,
        "axes.grid":           False,
        "grid.alpha":          0.28,
        "grid.linewidth":      0.45,
        "grid.color":          "#CCCCCC",
        "figure.dpi":          150,
        "savefig.dpi":         300,
        "savefig.bbox":        "tight",
        "savefig.pad_inches":  0.04,
        "figure.facecolor":    "white",
        "axes.facecolor":      "white",
    })


def format_percent_axis(ax: plt.Axes, axis: str = "y") -> None:
    """Format axis ticks as integer percentages."""
    fmt = mticker.FuncFormatter(lambda x, _: f"{x:.0f}%")
    if axis == "y":
        ax.yaxis.set_major_formatter(fmt)
    else:
        ax.xaxis.set_major_formatter(fmt)


def hgrid(ax: plt.Axes) -> None:
    """Light horizontal grid."""
    ax.set_axisbelow(True)
    ax.grid(axis="y", color="#CCCCCC", linewidth=0.45, alpha=0.3, zorder=0)


def save_figure(fig: plt.Figure, out_dir: Path, name: str) -> None:
    """Save PNG + PDF, create directory if needed."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        p = out_dir / f"{name}.{ext}"
        fig.savefig(p, dpi=300, bbox_inches="tight", pad_inches=0.04)
        print(f"  → {p.relative_to(ROOT)}")


def _load_comparison_csv() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse results_en_ko_comparison.csv with two ## sections."""
    text = (DATA_KO / "results_en_ko_comparison.csv").read_text()
    sections: dict[str, pd.DataFrame] = {}
    cur, buf = None, []
    for ln in text.splitlines():
        if ln.startswith("## "):
            if cur and buf:
                sections[cur] = pd.read_csv(StringIO("\n".join(buf)))
            cur, buf = ln[3:].strip(), []
        elif ln.strip():
            buf.append(ln)
    if cur and buf:
        sections[cur] = pd.read_csv(StringIO("\n".join(buf)))

    incon_key = next(k for k in sections if "Inconsistency" in k or "분석1" in k)
    cat_key   = next(k for k in sections if "Score Gap" in k or "분석2" in k or "카테고리" in k)
    return sections[incon_key], sections[cat_key]


def _row(df: pd.DataFrame, judge: str, col: str) -> float:
    return float(df.loc[df.judge == judge, col].iloc[0])


def _load_bias_breakdown() -> dict[str, dict[str, dict[str, float]]]:
    """
    Parse raw pairwise JSONL files to get 3-way bias breakdown
    among inconsistent cases (% of inconsistent):
        1st-pos bias  : winner_ab=="A" and winner_ba=="A"
        2nd-pos bias  : winner_ab=="B" and winner_ba=="B"
        Tie / mix     : remaining inconsistent

    Returns: {judge: {"EN": {"fp":%, "sp":%, "mix":%}, "KO": {...}}}
    """
    result: dict[str, dict[str, dict[str, float]]] = {}
    for judge, (en_sub, ko_sub) in PAIRWISE_DIRS.items():
        result[judge] = {}
        for lang, base, sub in [("EN", "en", en_sub), ("KO", "ko", ko_sub)]:
            d = ROOT / "data" / base / "judgments" / sub / "pairwise"
            incon = fp = sp = mix = 0
            if d.exists():
                for fpath in sorted(d.glob("*.jsonl")):
                    try:
                        lines = open(fpath, encoding="utf-8").read().splitlines()
                    except OSError:
                        continue
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            r = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if r.get("winner") != "inconsistent":
                            continue
                        incon += 1
                        ab, ba = r.get("winner_ab"), r.get("winner_ba")
                        if ab == "A" and ba == "A":
                            fp += 1
                        elif ab == "B" and ba == "B":
                            sp += 1
                        else:
                            mix += 1
            if incon > 0:
                result[judge][lang] = {
                    "fp":  fp  / incon * 100,
                    "sp":  sp  / incon * 100,
                    "mix": mix / incon * 100,
                }
            else:
                result[judge][lang] = {"fp": 0.0, "sp": 0.0, "mix": 0.0}
    return result


# ═════════════════════════════════════════════════════════════════════════════
# Fig 1 — Inconsistency Rate: Qwen Scaling + Cross-family Comparison
# ═════════════════════════════════════════════════════════════════════════════

def plot_fig1_inconsistency_rate(df: pd.DataFrame) -> None:
    """
    (a) Line plot: Qwen 7B→14B→32B scaling trend (EN vs KO).
    (b) Grouped bar: Qwen-32B (ref) / EXAONE-32B / GPT-4o-mini.
    KIPS full-width (170 mm).
    """
    fig, (ax_l, ax_r) = plt.subplots(
        1, 2, figsize=(W_FULL, 2.75),
        gridspec_kw={"width_ratios": [3, 2], "wspace": 0.30},
    )

    y_max = 92
    for ax in (ax_l, ax_r):
        ax.set_ylim(0, y_max)
        ax.yaxis.set_major_locator(mticker.MultipleLocator(20))
        format_percent_axis(ax, "y")
        hgrid(ax)

    # ── (a) Qwen scaling ────────────────────────────────────────────────────
    x_pos   = [0, 1, 2]
    x_labels = ["7B", "14B", "32B"]
    en_q = [_row(df, j, "en_incon_pct") for j in QWEN_JUDGES]
    ko_q = [_row(df, j, "ko_incon_pct") for j in QWEN_JUDGES]

    mk_kw = dict(markersize=5.5, markeredgecolor="white", markeredgewidth=0.7,
                 clip_on=False)
    ax_l.plot(x_pos, en_q, color=C_EN, lw=1.8, marker="o",
              label="English", zorder=4, **mk_kw)
    ax_l.plot(x_pos, ko_q, color=C_KO, lw=1.8, marker="o",
              label="Korean",  zorder=4, **mk_kw)

    # Endpoint drop annotation
    for vals, col in [(en_q, C_EN), (ko_q, C_KO)]:
        drop = vals[0] - vals[-1]
        ax_l.text(2.07, vals[-1], f"−{drop:.1f}%p",
                  ha="left", va="center", fontsize=6.5, color=col)

    ax_l.set_xticks(x_pos)
    ax_l.set_xticklabels(["Qwen-7B", "Qwen-14B", "Qwen-32B"], fontsize=7)
    ax_l.set_xlim(-0.30, 2.65)
    ax_l.set_ylabel("Inconsistency Rate", labelpad=4)
    ax_l.legend(loc="upper right", frameon=True, handlelength=1.1)
    ax_l.set_title("(a)  Same-family scaling", fontsize=7.5,
                   pad=5, color="#444444", loc="left", style="italic")

    # ── (b) Cross-family bars ────────────────────────────────────────────────
    cross_judges = ["qwen_32B", "exaone_32B", "gpt4omini"]
    cross_labels = ["Qwen-32B\n(ref.)", "EXAONE-32B", "GPT-4o-mini"]
    x_c = np.arange(len(cross_judges))
    w   = 0.28

    en_c = [_row(df, j, "en_incon_pct") for j in cross_judges]
    ko_c = [_row(df, j, "ko_incon_pct") for j in cross_judges]
    alphas = [0.50, 0.88, 0.88]

    for i, (ev, kv, al) in enumerate(zip(en_c, ko_c, alphas)):
        ax_r.bar(i - w / 2, ev, w, color=C_EN, alpha=al, zorder=3,
                 edgecolor="white", linewidth=0.3)
        ax_r.bar(i + w / 2, kv, w, color=C_KO, alpha=al, zorder=3,
                 edgecolor="white", linewidth=0.3)
        ax_r.text(i - w / 2, ev + 0.7, f"{ev:.1f}",
                  ha="center", va="bottom", fontsize=6, color=C_EN)
        ax_r.text(i + w / 2, kv + 0.7, f"{kv:.1f}",
                  ha="center", va="bottom", fontsize=6, color=C_KO)

    ax_r.set_xticks(x_c)
    ax_r.set_xticklabels(cross_labels, fontsize=7)
    ax_r.tick_params(axis="y", labelleft=False)
    ax_r.spines["left"].set_visible(False)
    ax_r.set_title("(b)  Cross-family judges", fontsize=7.5,
                   pad=5, color="#444444", loc="left", style="italic")

    handles = [mpatches.Patch(color=C_EN, label="English"),
               mpatches.Patch(color=C_KO, label="Korean")]
    ax_r.legend(handles=handles, loc="upper right", frameon=True, handlelength=1.0)

    save_figure(fig, OUT, "fig1_inconsistency_rate")
    plt.close(fig)


# ═════════════════════════════════════════════════════════════════════════════
# Fig 2 — Position Bias Breakdown (among inconsistent cases, 3-way)
# ═════════════════════════════════════════════════════════════════════════════

def plot_fig2_position_bias_breakdown(bias: dict) -> None:
    """
    Two panels (English | Korean).
    y-axis: share of inconsistent cases (%).
    Stacks (bottom→top): Tie/Mix (gray) | 2nd-pos bias (amber) | 1st-pos bias (red).
    Consistent segment removed entirely. Parsed from raw pairwise JSONL.
    KIPS full-width (170 mm).
    """
    fig, axes = plt.subplots(
        1, 2, figsize=(W_FULL, 2.75), sharey=True,
        gridspec_kw={"wspace": 0.06},
    )

    x          = np.arange(len(ALL_JUDGES))
    bar_w      = 0.52
    xlabels    = ["Qwen-7B", "Qwen-14B", "Qwen-32B", "EXAONE-32B", "GPT-4o-mini"]

    for ax, lang, title in [(axes[0], "EN", "(a)  English"),
                             (axes[1], "KO", "(b)  Korean")]:
        fp_arr  = np.array([bias[j][lang]["fp"]  for j in ALL_JUDGES])
        sp_arr  = np.array([bias[j][lang]["sp"]  for j in ALL_JUDGES])
        mix_arr = np.array([bias[j][lang]["mix"] for j in ALL_JUDGES])

        # Stack: mix (bottom) → 2nd-pos → 1st-pos (top)
        ax.bar(x, mix_arr, bar_w, color=C_MIX, zorder=3,
               edgecolor="white", linewidth=0.3, label="Tie / mix")
        ax.bar(x, sp_arr, bar_w, bottom=mix_arr, color=C_SP, zorder=3,
               edgecolor="white", linewidth=0.3, label="2nd-pos bias")
        ax.bar(x, fp_arr, bar_w, bottom=mix_arr + sp_arr, color=C_FP, zorder=3,
               edgecolor="white", linewidth=0.3, label="1st-pos bias")

        # 1st-pos value label (white, inside top segment if tall enough)
        for i, (fp_v, sp_v, mix_v) in enumerate(zip(fp_arr, sp_arr, mix_arr)):
            if fp_v >= 12:
                ax.text(i, mix_v + sp_v + fp_v / 2, f"{fp_v:.0f}%",
                        ha="center", va="center", fontsize=6,
                        color="white", fontweight="bold")

        ax.axvline(2.5, color="#AAAAAA", lw=0.7, ls="--", alpha=0.5, zorder=2)
        ax.set_xticks(x)
        ax.set_xticklabels(xlabels, fontsize=7, rotation=18, ha="right")
        ax.set_title(title, fontsize=7.5, pad=5, color="#444444",
                     loc="left", style="italic")
        hgrid(ax)

    axes[0].set_ylim(0, 108)
    axes[0].yaxis.set_major_locator(mticker.MultipleLocator(25))
    format_percent_axis(axes[0], "y")
    axes[0].set_ylabel("Share among inconsistent cases", labelpad=4)
    axes[1].tick_params(axis="y", left=False)
    axes[1].spines["left"].set_visible(False)

    handles = [
        mpatches.Patch(color=C_FP,  label="1st-pos bias"),
        mpatches.Patch(color=C_SP,  label="2nd-pos bias"),
        mpatches.Patch(color=C_MIX, label="Tie / mix"),
    ]
    axes[1].legend(handles=handles, loc="upper right", frameon=True,
                   ncol=1, handlelength=1.0)

    save_figure(fig, OUT, "fig2_position_bias_breakdown")
    plt.close(fig)


# ═════════════════════════════════════════════════════════════════════════════
# Fig 3 — (removed)
# §5.2 모델별 EN vs KO 점수는 6개 모델이라 scatter보다 논문 표 + 하이라이트가 더 적절.
# 필요 시 아래 함수를 활성화해 slope chart로 대체 가능.
# ═════════════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════════════
# Fig 4 — Category-level EN-KO Score Gap (Qwen-32B judge)
# ═════════════════════════════════════════════════════════════════════════════

def plot_fig4_category_gap(cat_df: pd.DataFrame) -> None:
    """
    Horizontal diverging bar.
    Sorted: most-negative gap at top.
    x = KO − EN.  No legend.  Value labels inside bars.
    KIPS single-column (82 mm).
    """
    sub = cat_df[cat_df["judge"] == "qwen_32B"].copy()
    sub = sub.sort_values("delta", ascending=False)   # top = most negative in barh

    cats   = [CAT_DISPLAY.get(c, c) for c in sub["category"]]
    deltas = sub["delta"].tolist()

    fig, ax = plt.subplots(figsize=(W_HALF, 3.10))

    bars = ax.barh(cats, deltas, height=0.55, color=C_BAR,
                   alpha=0.82, zorder=3, edgecolor="white", linewidth=0.3)

    ax.axvline(0, color="#AAAAAA", lw=0.8, zorder=2)

    for bar, v in zip(bars, deltas):
        ax.text(v / 2, bar.get_y() + bar.get_height() / 2,
                f"{v:.2f}",
                ha="center", va="center", fontsize=6.5, color="white")

    ax.set_axisbelow(True)
    ax.grid(axis="x", color="#CCCCCC", linewidth=0.45, alpha=0.3, zorder=0)
    ax.set_xlabel("Score Gap  (Korean − English)", labelpad=4)
    ax.set_xlim(-2.35, 0.28)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(0.5))
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0, pad=5)
    ax.yaxis.grid(False)
    ax.text(0.98, 0.015, "Qwen-32B judge", transform=ax.transAxes,
            fontsize=6, color="#999999", ha="right", va="bottom", style="italic")

    fig.tight_layout(pad=0.4)
    save_figure(fig, OUT, "fig4_category_gap")
    plt.close(fig)


# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════

def main() -> None:
    set_paper_style()

    print("Loading CSV data …")
    incon_df, cat_df = _load_comparison_csv()

    print("Parsing raw pairwise JSONL for 3-way bias breakdown …")
    bias = _load_bias_breakdown()

    print(f"\nGenerating figures → {OUT.relative_to(ROOT)}/")
    plot_fig1_inconsistency_rate(incon_df)
    plot_fig2_position_bias_breakdown(bias)
    # Fig 3 (EN vs KO scatter) removed: 6개 모델은 표 + 하이라이트로 대체
    plot_fig4_category_gap(cat_df)

    print("\nDone.")


if __name__ == "__main__":
    main()
