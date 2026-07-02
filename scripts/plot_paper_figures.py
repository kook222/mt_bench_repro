#!/usr/bin/env python3
"""
scripts/plot_paper_figures.py

ACL/EMNLP-style publication figures for Korean MT-Bench paper.

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

# ── Color palette (Okabe-Ito colorblind-friendly) ─────────────────────────────
C_EN    = "#0072B2"   # blue    – English / general-purpose
C_KO    = "#D55E00"   # vermillion – Korean / Korean-specialized
C_FP    = "#D55E00"   # 1st-position bias (vermillion)
C_OTHER = "#BBBBBB"   # other inconsistent (light gray)
C_BAR   = "#4878CF"   # muted blue – neutral bar (Fig 4)

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
JUDGE_SHORT = {
    "qwen_7B":    "7B",
    "qwen_14B":   "14B",
    "qwen_32B":   "32B",
    "exaone_32B": "EXAONE-32B",
    "gpt4omini":  "GPT-4o-mini",
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
    """Global matplotlib rcParams for publication-quality figures."""
    plt.rcParams.update({
        "font.family":         "DejaVu Sans",
        "font.size":           9,
        "axes.labelsize":      9,
        "axes.titlesize":      9,
        "xtick.labelsize":     8,
        "ytick.labelsize":     8,
        "legend.fontsize":     8,
        "legend.framealpha":   0.95,
        "legend.edgecolor":    "#DDDDDD",
        "legend.borderpad":    0.5,
        "legend.handlelength": 1.4,
        "legend.handleheight": 0.8,
        "axes.spines.top":     False,
        "axes.spines.right":   False,
        "axes.linewidth":      0.7,
        "xtick.major.width":   0.7,
        "ytick.major.width":   0.7,
        "xtick.major.size":    3.0,
        "ytick.major.size":    3.0,
        "axes.grid":           False,
        "grid.alpha":          0.3,
        "grid.linewidth":      0.5,
        "grid.color":          "#CCCCCC",
        "figure.dpi":          150,
        "savefig.dpi":         300,
        "savefig.bbox":        "tight",
        "savefig.pad_inches":  0.05,
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
    """Light horizontal grid; keeps bars/lines in foreground."""
    ax.set_axisbelow(True)
    ax.grid(axis="y", color="#CCCCCC", linewidth=0.5, alpha=0.35, zorder=0)


def save_figure(fig: plt.Figure, out_dir: Path, name: str) -> None:
    """Save to PNG and PDF, create directory if needed, print paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        p = out_dir / f"{name}.{ext}"
        fig.savefig(p, dpi=300, bbox_inches="tight", pad_inches=0.05)
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


# ═════════════════════════════════════════════════════════════════════════════
# Fig 1 — Inconsistency Rate: Qwen Scaling + Cross-family Comparison
# ═════════════════════════════════════════════════════════════════════════════

def plot_fig1_inconsistency_rate(df: pd.DataFrame) -> None:
    """
    (a) Line plot: Qwen 7B→14B→32B scaling trend (EN vs KO).
    (b) Grouped bar: cross-family judges (EXAONE-32B, GPT-4o-mini) with
        Qwen-32B as reference.
    """
    fig, (ax_l, ax_r) = plt.subplots(
        1, 2, figsize=(9.0, 3.8),
        gridspec_kw={"width_ratios": [3, 2], "wspace": 0.32},
    )

    y_max = 92
    for ax in (ax_l, ax_r):
        ax.set_ylim(0, y_max)
        ax.yaxis.set_major_locator(mticker.MultipleLocator(20))
        format_percent_axis(ax, "y")
        hgrid(ax)

    # ── (a) Qwen scaling: line plot ─────────────────────────────────────────
    x_pos = [0, 1, 2]
    x_labels = ["7B", "14B", "32B"]
    en_q = [_row(df, j, "en_incon_pct") for j in QWEN_JUDGES]
    ko_q = [_row(df, j, "ko_incon_pct") for j in QWEN_JUDGES]

    mk_kw = dict(markersize=7, markeredgecolor="white", markeredgewidth=0.8,
                 clip_on=False)
    ax_l.plot(x_pos, en_q, color=C_EN, lw=2.2, marker="o",
              label="English", zorder=4, **mk_kw)
    ax_l.plot(x_pos, ko_q, color=C_KO, lw=2.2, marker="o",
              label="Korean",  zorder=4, **mk_kw)

    # Annotate total drop (7B → 32B) at the right endpoint
    for y_line, vals, col, va_pos in [
        (en_q, en_q, C_EN, "bottom"),
        (ko_q, ko_q, C_KO, "top"),
    ]:
        drop = vals[0] - vals[-1]
        ax_l.annotate(
            f"−{drop:.1f}%p",
            xy=(2, vals[-1]),
            xytext=(2.08, vals[-1]),
            ha="left", va="center", fontsize=7, color=col, zorder=5,
        )

    ax_l.set_xticks(x_pos)
    ax_l.set_xticklabels(x_labels, fontsize=8.5)
    ax_l.set_xlim(-0.35, 2.7)
    ax_l.set_ylabel("Inconsistency Rate", labelpad=5)
    ax_l.legend(loc="upper right", frameon=True, handlelength=1.2, fontsize=8)
    ax_l.set_title("(a)  Same-family: Qwen scaling", fontsize=9,
                   pad=7, color="#333333", loc="left", style="italic")
    ax_l.spines["bottom"].set_linewidth(0.7)

    # ── (b) Cross-family comparison: grouped bars ────────────────────────────
    cross_judges = ["qwen_32B", "exaone_32B", "gpt4omini"]
    cross_labels = ["Qwen-32B\n(ref.)", "EXAONE-32B", "GPT-4o-mini"]
    x_c = np.arange(len(cross_judges))
    w   = 0.30

    en_c = [_row(df, j, "en_incon_pct") for j in cross_judges]
    ko_c = [_row(df, j, "ko_incon_pct") for j in cross_judges]

    # Qwen-32B reference bars get lighter alpha
    alphas = [0.55, 0.90, 0.90]
    for i, (ev, kv, al) in enumerate(zip(en_c, ko_c, alphas)):
        ax_r.bar(i - w / 2, ev, w, color=C_EN, alpha=al, zorder=3,
                 edgecolor="white", linewidth=0.4)
        ax_r.bar(i + w / 2, kv, w, color=C_KO, alpha=al, zorder=3,
                 edgecolor="white", linewidth=0.4)
        # Value labels above bars
        ax_r.text(i - w / 2, ev + 0.8, f"{ev:.1f}",
                  ha="center", va="bottom", fontsize=7, color=C_EN)
        ax_r.text(i + w / 2, kv + 0.8, f"{kv:.1f}",
                  ha="center", va="bottom", fontsize=7, color=C_KO)

    ax_r.set_xticks(x_c)
    ax_r.set_xticklabels(cross_labels, fontsize=8)
    ax_r.tick_params(axis="y", labelleft=False)
    ax_r.spines["left"].set_visible(False)
    ax_r.set_title("(b)  Cross-family judges", fontsize=9,
                   pad=7, color="#333333", loc="left", style="italic")

    # Shared legend proxy for EN/KO in right panel
    handles = [
        mpatches.Patch(color=C_EN, label="English"),
        mpatches.Patch(color=C_KO, label="Korean"),
    ]
    ax_r.legend(handles=handles, loc="upper right", frameon=True,
                fontsize=8, handlelength=1.0)

    save_figure(fig, OUT, "fig1_inconsistency_rate")
    plt.close(fig)


# ═════════════════════════════════════════════════════════════════════════════
# Fig 2 — Position Bias Breakdown (among inconsistent cases only)
# ═════════════════════════════════════════════════════════════════════════════

def plot_fig2_position_bias_breakdown(df: pd.DataFrame) -> None:
    """
    Two panels (English | Korean).
    y-axis: share of inconsistent cases (%).
    Stacks: 1st-position bias (red) over Other inconsistent (gray).
    Consistent segment removed entirely.
    """
    fig, axes = plt.subplots(
        1, 2, figsize=(8.0, 3.8), sharey=True,
        gridspec_kw={"wspace": 0.06},
    )

    x     = np.arange(len(ALL_JUDGES))
    bar_w = 0.55
    short_labels = ["Qwen-7B", "Qwen-14B", "Qwen-32B", "EXAONE-32B", "GPT-4o-mini"]

    panels = [
        (axes[0], "en_incon_pct", "en_fp_pct", "(a)  English"),
        (axes[1], "ko_incon_pct", "ko_fp_pct", "(b)  Korean"),
    ]
    for ax, ic_col, fp_col, title in panels:
        fp_share, oth_share = [], []
        for j in ALL_JUDGES:
            ic = _row(df, j, ic_col)
            fp = _row(df, j, fp_col)
            if ic > 0:
                fp_share.append(fp / ic * 100)
                oth_share.append((ic - fp) / ic * 100)
            else:
                fp_share.append(0.0)
                oth_share.append(0.0)

        fp_arr  = np.array(fp_share)
        oth_arr = np.array(oth_share)

        ax.bar(x, oth_arr, bar_w, color=C_OTHER, zorder=3,
               edgecolor="white", linewidth=0.3, label="Other inconsistent")
        ax.bar(x, fp_arr, bar_w, bottom=oth_arr, color=C_FP, zorder=3,
               edgecolor="white", linewidth=0.3, label="1st-pos bias")

        # Value label inside 1st-pos bias segment (white, if segment tall enough)
        for i, (fp_v, oth_v) in enumerate(zip(fp_arr, oth_arr)):
            if fp_v >= 10:
                ax.text(i, oth_v + fp_v / 2, f"{fp_v:.0f}%",
                        ha="center", va="center", fontsize=7,
                        color="white", fontweight="bold")

        # Separator: same-family | cross-family
        ax.axvline(2.5, color="#AAAAAA", lw=0.8, ls="--", alpha=0.55, zorder=2)

        ax.set_xticks(x)
        ax.set_xticklabels(short_labels, fontsize=7.5, rotation=20, ha="right")
        ax.set_title(title, fontsize=9, pad=7, color="#333333",
                     loc="left", style="italic")
        hgrid(ax)
        ax.spines["bottom"].set_linewidth(0.7)

    axes[0].set_ylim(0, 110)
    axes[0].yaxis.set_major_locator(mticker.MultipleLocator(25))
    format_percent_axis(axes[0], "y")
    axes[0].set_ylabel("Share among inconsistent cases", labelpad=5)
    axes[1].tick_params(axis="y", left=False)
    axes[1].spines["left"].set_visible(False)

    handles = [
        mpatches.Patch(color=C_FP,    label="1st-position bias"),
        mpatches.Patch(color=C_OTHER, label="Other inconsistent"),
    ]
    axes[1].legend(handles=handles, loc="upper right", frameon=True, fontsize=8)

    save_figure(fig, OUT, "fig2_position_bias_breakdown")
    plt.close(fig)


# ═════════════════════════════════════════════════════════════════════════════
# Fig 3 — EN vs KO Score Scatter (Qwen-32B judge)
# ═════════════════════════════════════════════════════════════════════════════

def plot_fig3_en_ko_score_scatter() -> None:
    """
    x = English average score, y = Korean average score (Qwen-32B judge).
    y=x diagonal reference line; all 6 eval models as labeled scatter points.
    Korean-specialized: diamond markers (red).
    General-purpose: square markers (blue).
    """
    en_df = pd.read_csv(DATA_EN / "results_phase3_judge_32B.csv")
    ko_df = pd.read_csv(DATA_KO / "results_ko_judge_32B.csv")

    points = []
    for _, row in en_df.iterrows():
        model  = row["model"]
        ko_row = ko_df[ko_df.model == model]
        if ko_row.empty:
            continue
        en_s = float(row["overall"])
        ko_s = float(ko_row["overall"].iloc[0])
        points.append({
            "name":  MODEL_SHORT.get(model, model),
            "en":    en_s,
            "ko":    ko_s,
            "delta": ko_s - en_s,
            "is_ko": model in KO_SPEC,
        })

    # Manual label offsets (dx, dy, ha, va) — tuned to avoid overlaps
    # Data: EEVE(6.72,6.38), EXAONE(8.32,8.09), Llama(7.71,5.79),
    #       Mistral(7.09,4.73), Phi(8.06,5.52), Gemma(8.09,7.35)
    offsets: dict[str, tuple[float, float, str, str]] = {
        "EEVE-10.8B":   (-0.08, +0.22, "center", "bottom"),
        "EXAONE-7.8B":  (+0.08, +0.18, "left",   "bottom"),
        "Llama-3.1-8B": (+0.08, +0.12, "left",   "bottom"),
        "Mistral-7B":   (+0.08, -0.16, "left",   "top"),
        "Phi-3.5-mini": (+0.08, +0.12, "left",   "bottom"),
        "Gemma-2-9B":   (+0.08, +0.15, "left",   "bottom"),
    }

    lim_lo, lim_hi = 3.6, 9.4
    fig, ax = plt.subplots(figsize=(5.4, 5.4))

    # y=x diagonal + below-diagonal shading
    ax.plot([lim_lo, lim_hi], [lim_lo, lim_hi],
            color="#CCCCCC", lw=1.0, ls="--", zorder=1)
    ax.fill_between([lim_lo, lim_hi], [lim_lo, lim_hi], lim_lo,
                    color="#F7F7F7", zorder=0)
    ax.text(8.55, 8.85, "$y = x$", color="#BBBBBB", fontsize=7.5,
            ha="center", va="bottom", rotation=39, rotation_mode="anchor")

    for p in points:
        col = C_KO if p["is_ko"] else C_EN
        mk  = "D"  if p["is_ko"] else "s"
        ax.scatter(p["en"], p["ko"], color=col, s=58, zorder=4,
                   marker=mk, edgecolors="white", linewidths=0.8)

        dx, dy, ha, va = offsets.get(p["name"], (0.08, 0.12, "left", "bottom"))
        fw    = "bold" if p["is_ko"] else "normal"
        label = f"{p['name']}  (Δ{p['delta']:+.2f})"
        use_arrow = (abs(dx) > 0.18 or abs(dy) > 0.18)
        ax.annotate(
            label,
            xy=(p["en"], p["ko"]),
            xytext=(p["en"] + dx, p["ko"] + dy),
            ha=ha, va=va, fontsize=7.5, color=col, fontweight=fw,
            arrowprops=(dict(arrowstyle="-", color=col, lw=0.5,
                             shrinkA=4, shrinkB=2)
                        if use_arrow else None),
        )

    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(lim_lo, lim_hi)
    ax.set_ylim(lim_lo, lim_hi)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(1))
    ax.yaxis.set_major_locator(mticker.MultipleLocator(1))
    ax.set_xlabel("English Score  (Qwen-32B judge)", labelpad=5)
    ax.set_ylabel("Korean Score  (Qwen-32B judge)",  labelpad=5)
    # Light grid on both axes for readability in a scatter plot
    ax.set_axisbelow(True)
    ax.grid(color="#CCCCCC", linewidth=0.5, alpha=0.35, zorder=0)

    handles = [
        mlines.Line2D([], [], color=C_KO, lw=0, marker="D", ms=6,
                      markeredgecolor="white", markeredgewidth=0.7,
                      label="Korean-specialized"),
        mlines.Line2D([], [], color=C_EN, lw=0, marker="s", ms=6,
                      markeredgecolor="white", markeredgewidth=0.7,
                      label="General-purpose"),
    ]
    ax.legend(handles=handles, loc="upper left", frameon=True,
              fontsize=8, handlelength=0.8)

    save_figure(fig, OUT, "fig3_en_ko_score_scatter")
    plt.close(fig)


# ═════════════════════════════════════════════════════════════════════════════
# Fig 4 — Category-level EN-KO Score Gap (Qwen-32B judge)
# ═════════════════════════════════════════════════════════════════════════════

def plot_fig4_category_gap(cat_df: pd.DataFrame) -> None:
    """
    Horizontal diverging bar chart.
    Sorted by gap magnitude — most negative gap at top.
    x = KO − EN (all negative in this dataset).
    No legend; value labels centered inside bars.
    """
    sub = cat_df[cat_df["judge"] == "qwen_32B"].copy()
    # ascending=False → least negative first (bottom), most negative last (top) in barh
    sub = sub.sort_values("delta", ascending=False)

    cats   = [CAT_DISPLAY.get(c, c) for c in sub["category"]]
    deltas = sub["delta"].tolist()

    fig, ax = plt.subplots(figsize=(6.2, 4.0))

    bars = ax.barh(cats, deltas, height=0.58, color=C_BAR,
                   alpha=0.82, zorder=3, edgecolor="white", linewidth=0.3)

    # x=0 reference line (light, thin)
    ax.axvline(0, color="#AAAAAA", lw=0.9, zorder=2)

    # Value labels centered inside each bar (white text)
    for bar, v in zip(bars, deltas):
        ax.text(v / 2, bar.get_y() + bar.get_height() / 2,
                f"{v:.2f}",
                ha="center", va="center", fontsize=7.5,
                color="white", fontweight="normal")

    # Light horizontal grid (x-direction for horizontal bars)
    ax.set_axisbelow(True)
    ax.grid(axis="x", color="#CCCCCC", linewidth=0.5, alpha=0.35, zorder=0)

    ax.set_xlabel("Score Gap  (Korean − English)", labelpad=5)
    ax.set_xlim(-2.35, 0.28)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(0.5))
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0, pad=6)
    ax.yaxis.grid(False)

    ax.text(0.98, 0.015, "Qwen-32B judge", transform=ax.transAxes,
            fontsize=7, color="#999999", ha="right", va="bottom", style="italic")

    fig.tight_layout(pad=0.5)
    save_figure(fig, OUT, "fig4_category_gap")
    plt.close(fig)


# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════

def main() -> None:
    set_paper_style()
    print("Loading data …")
    incon_df, cat_df = _load_comparison_csv()

    print(f"\nGenerating figures → {OUT.relative_to(ROOT)}/")
    plot_fig1_inconsistency_rate(incon_df)
    plot_fig2_position_bias_breakdown(incon_df)
    plot_fig3_en_ko_score_scatter()
    plot_fig4_category_gap(cat_df)

    print("\nDone.")


if __name__ == "__main__":
    main()
