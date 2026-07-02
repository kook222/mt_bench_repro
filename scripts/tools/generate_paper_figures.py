#!/usr/bin/env python3
"""
generate_paper_figures.py
Publication-quality figures for Korean MT-Bench paper (TKIPS).

Usage:
    cd mt_bench_repro
    python scripts/tools/generate_paper_figures.py
"""

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

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT    = Path(__file__).resolve().parents[2]
DATA_EN = ROOT / "data" / "en" / "results"
DATA_KO = ROOT / "data" / "ko" / "results"
OUT     = ROOT / "paper" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# ── Global style ─────────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family":          "DejaVu Sans",
    "font.size":            10,
    "axes.labelsize":       10,
    "axes.titlesize":       11,
    "xtick.labelsize":      9,
    "ytick.labelsize":      9,
    "legend.fontsize":      8.5,
    "legend.framealpha":    0.92,
    "legend.edgecolor":     "#CCCCCC",
    "legend.borderpad":     0.6,
    "axes.spines.top":      False,
    "axes.spines.right":    False,
    "axes.linewidth":       0.8,
    "xtick.major.width":    0.8,
    "ytick.major.width":    0.8,
    "axes.grid":            True,
    "grid.alpha":           0.30,
    "grid.linewidth":       0.6,
    "grid.color":           "#BBBBBB",
    "figure.dpi":           150,
    "savefig.dpi":          300,
    "savefig.bbox":         "tight",
    "savefig.pad_inches":   0.08,
})

# ── Color palette ─────────────────────────────────────────────────────────────
C_EN      = "#2166AC"   # deep blue  – English
C_KO      = "#B2182B"   # deep red   – Korean
C_KOSP    = "#B2182B"   # Korean-specialized models
C_GEN     = "#4393C3"   # mid blue   – general-purpose models
C_CONSIST = "#D0D0D0"   # light gray – consistent pairs
C_FP      = "#D6604D"   # coral red  – 1st-position bias
C_OTHER   = "#FDBF6F"   # amber      – other inconsistent
C_CODE    = "#D6604D"   # highlight for coding

JUDGE_ORDER  = ["qwen_7B", "qwen_14B", "qwen_32B", "exaone_32B", "gpt4omini"]
JUDGE_LABELS = {
    "qwen_7B":    "Qwen\n7B",
    "qwen_14B":   "Qwen\n14B",
    "qwen_32B":   "Qwen\n32B",
    "exaone_32B": "EXAONE\n32B",
    "gpt4omini":  "GPT-4o\nmini",
}
JUDGE_DISPLAY = {
    "qwen_7B":    "Qwen-7B",
    "qwen_14B":   "Qwen-14B",
    "qwen_32B":   "Qwen-32B",
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
    "writing": "Writing", "roleplay": "Roleplay", "reasoning": "Reasoning",
    "math": "Math", "coding": "Coding", "extraction": "Extraction",
    "stem": "STEM", "humanities": "Humanities",
}

# ── Data loading ──────────────────────────────────────────────────────────────

def load_comparison_csv():
    lines = (DATA_KO / "results_en_ko_comparison.csv").read_text().splitlines()
    sections, cur, buf = {}, None, []
    for ln in lines:
        if ln.startswith("## "):
            if cur: sections[cur] = pd.read_csv(StringIO("\n".join(buf)))
            cur, buf = ln[3:].strip(), []
        elif ln.strip():
            buf.append(ln)
    if cur: sections[cur] = pd.read_csv(StringIO("\n".join(buf)))
    return sections


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 1 — Inconsistency Rate: English vs Korean
# ═══════════════════════════════════════════════════════════════════════════════

def fig1_inconsistency(df):
    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    ax.set_axisbelow(True)
    ax.grid(axis="y", zorder=0)

    x = np.arange(len(JUDGE_ORDER))
    w = 0.32

    en_vals = [df.loc[df.judge == j, "en_incon_pct"].iloc[0] for j in JUDGE_ORDER]
    ko_vals = [df.loc[df.judge == j, "ko_incon_pct"].iloc[0] for j in JUDGE_ORDER]

    b_en = ax.bar(x - w / 2, en_vals, w, color=C_EN, label="English",
                  zorder=3, edgecolor="white", linewidth=0.4)
    b_ko = ax.bar(x + w / 2, ko_vals, w, color=C_KO, label="Korean",
                  zorder=3, edgecolor="white", linewidth=0.4)

    # Value labels inside bars
    for bar, v in zip(b_en, en_vals):
        ax.text(bar.get_x() + bar.get_width() / 2, v - 2.5,
                f"{v:.1f}", ha="center", va="top", fontsize=7.5,
                color="white", fontweight="bold")
    for bar, v in zip(b_ko, ko_vals):
        ax.text(bar.get_x() + bar.get_width() / 2, v - 2.5,
                f"{v:.1f}", ha="center", va="top", fontsize=7.5,
                color="white", fontweight="bold")

    # Δ annotations above pairs
    for i, (ev, kv) in enumerate(zip(en_vals, ko_vals)):
        delta = kv - ev
        top = max(ev, kv) + 2.0
        ax.annotate(
            f"Δ{delta:+.1f}%p",
            xy=(x[i], top), xytext=(x[i], top + 0.5),
            ha="center", va="bottom", fontsize=8, color="#444444",
            fontweight="bold",
        )

    # Separator: same-family vs cross-family
    ax.axvline(2.5, color="#AAAAAA", lw=1.0, ls="--", alpha=0.7, zorder=2)
    ax.text(1.0, 91, "Same-family judges", ha="center", fontsize=8,
            color="#777777", style="italic")
    ax.text(3.5, 91, "Cross-family judges", ha="center", fontsize=8,
            color="#777777", style="italic")

    ax.set_xticks(x)
    ax.set_xticklabels([JUDGE_LABELS[j] for j in JUDGE_ORDER], fontsize=9)
    ax.set_ylabel("Inconsistency Rate (%)", labelpad=6)
    ax.set_ylim(0, 98)
    ax.yaxis.set_major_locator(mticker.MultipleLocator(20))
    ax.legend(loc="upper right", frameon=True)
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_linewidth(0.8)

    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"fig1_inconsistency.{ext}")
    plt.close(fig)
    print("✓  fig1_inconsistency")


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 2 — Pairwise Verdict Composition (Stacked Bar)
# ═══════════════════════════════════════════════════════════════════════════════

def fig2_position_breakdown(df):
    """Consistent / 1st-position bias / Other inconsistent — 10 conditions."""
    fig, ax = plt.subplots(figsize=(9.0, 4.5))
    ax.set_axisbelow(True)

    labels, consist, fp, other = [], [], [], []
    for lang, ic_col, fp_col in [("EN", "en_incon_pct", "en_fp_pct"),
                                  ("KO", "ko_incon_pct", "ko_fp_pct")]:
        for j in JUDGE_ORDER:
            row  = df[df.judge == j].iloc[0]
            ic   = row[ic_col]
            f    = row[fp_col]
            labels.append(f"{JUDGE_DISPLAY[j]}\n({lang})")
            consist.append(100 - ic)
            fp.append(f)
            other.append(ic - f)

    x = np.arange(len(labels))
    consist = np.array(consist)
    fp      = np.array(fp)
    other   = np.array(other)

    ax.bar(x, consist, color=C_CONSIST, label="Consistent",          zorder=3,
           edgecolor="white", linewidth=0.3)
    ax.bar(x, other,   bottom=consist, color=C_OTHER,
           label="Other inconsistent", zorder=3, edgecolor="white", linewidth=0.3)
    ax.bar(x, fp,      bottom=consist + other, color=C_FP,
           label="1st-position bias", zorder=3, edgecolor="white", linewidth=0.3)

    # 1st-pos % label inside top segment (only if segment tall enough)
    for i, (c, o, f) in enumerate(zip(consist, other, fp)):
        if f >= 3:
            ax.text(x[i], c + o + f / 2, f"{f:.1f}",
                    ha="center", va="center", fontsize=7, color="white",
                    fontweight="bold")

    # Language group separators + labels
    ax.axvline(4.5, color="#888888", lw=1.2, ls="--", alpha=0.75, zorder=4)
    for xc, label, color in [(2.0, "English", C_EN), (7.0, "Korean", C_KO)]:
        ax.text(xc, 104, label, ha="center", fontsize=10.5,
                fontweight="bold", color=color)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7.8)
    ax.set_ylabel("Percentage of All Pairwise Pairs (%)", labelpad=6)
    ax.set_ylim(0, 111)
    ax.yaxis.set_major_locator(mticker.MultipleLocator(25))
    ax.grid(axis="y", zorder=0)
    ax.legend(loc="upper right", ncol=1, frameon=True)
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_linewidth(0.8)

    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"fig2_position_breakdown.{ext}")
    plt.close(fig)
    print("✓  fig2_position_breakdown")


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 3 — EN vs KO Score: Slope Chart (Qwen-32B judge)
# ═══════════════════════════════════════════════════════════════════════════════

def fig3_score_slope():
    en_df = pd.read_csv(DATA_EN / "results_phase3_judge_32B.csv")
    ko_df = pd.read_csv(DATA_KO / "results_ko_judge_32B.csv")

    models = en_df["model"].tolist()

    # Collect all data first for label-collision handling
    data = []
    for model in models:
        en_row = en_df[en_df.model == model]
        ko_row = ko_df[ko_df.model == model]
        if en_row.empty or ko_row.empty:
            continue
        data.append({
            "model": model,
            "en":    float(en_row["overall"].iloc[0]),
            "ko":    float(ko_row["overall"].iloc[0]),
            "is_ko": model in KO_SPEC,
        })

    # Sort by EN score for consistent left-side positioning
    data.sort(key=lambda d: d["en"])

    fig, ax = plt.subplots(figsize=(6.2, 5.4))
    ax.set_axisbelow(True)
    ax.grid(axis="y", zorder=0)

    x_en, x_ko = 0.0, 1.0

    # Resolve KO label positions (avoid vertical overlap)
    ko_positions = []
    for d in data:
        ko_positions.append(d["ko"])
    ko_positions = _resolve_label_positions(ko_positions, min_gap=0.28)

    for i, d in enumerate(data):
        model = d["model"]
        en_s  = d["en"]
        ko_s  = d["ko"]
        is_ko = d["is_ko"]
        col   = C_KOSP if is_ko else C_GEN
        lw    = 2.2 if is_ko else 1.5
        mk    = "o" if is_ko else "s"
        ms    = 72  if is_ko else 52

        ax.plot([x_en, x_ko], [en_s, ko_s], color=col, lw=lw, zorder=3,
                alpha=0.9, solid_capstyle="round")
        ax.scatter([x_en, x_ko], [en_s, ko_s], color=col, s=ms, zorder=4,
                   marker=mk, edgecolors="white", linewidths=0.7)

        # Right-side labels (collision-resolved y position)
        delta    = ko_s - en_s
        name     = MODEL_SHORT.get(model, model)
        label_y  = ko_positions[i]
        ax.annotate(
            f"{name}  (Δ{delta:+.2f})",
            xy=(x_ko, ko_s), xytext=(x_ko + 0.06, label_y),
            ha="left", va="center", fontsize=8.0, color=col,
            fontweight="bold" if is_ko else "normal",
            arrowprops=dict(arrowstyle="-", color=col, lw=0.6,
                            shrinkA=4, shrinkB=2)
            if abs(label_y - ko_s) > 0.12 else None,
        )

    # Axes
    ax.set_xlim(-0.18, 2.10)
    ax.set_ylim(3.8, 9.5)
    ax.set_xticks([x_en, x_ko])
    ax.set_xticklabels(["English", "Korean"], fontsize=12, fontweight="bold")
    ax.set_ylabel("Average Score  (Qwen-32B judge)", labelpad=6)
    ax.tick_params(axis="x", length=0, pad=8)
    ax.spines["bottom"].set_visible(False)
    ax.yaxis.set_major_locator(mticker.MultipleLocator(1))

    handles = [
        mlines.Line2D([], [], color=C_KOSP, lw=2.2, marker="o", ms=7,
                      markeredgecolor="white", label="Korean-specialized"),
        mlines.Line2D([], [], color=C_GEN,  lw=1.5, marker="s", ms=6,
                      markeredgecolor="white", label="General-purpose"),
    ]
    ax.legend(handles=handles, loc="upper right", frameon=True)

    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"fig3_score_scatter.{ext}")
    plt.close(fig)
    print("✓  fig3_score_slope")


def _resolve_label_positions(ys, min_gap=0.25):
    """Push label positions apart so no two are closer than min_gap."""
    ys = list(ys)
    pairs = sorted(enumerate(ys), key=lambda t: t[1])
    for _ in range(50):
        moved = False
        for k in range(len(pairs) - 1):
            ia, ya = pairs[k]
            ib, yb = pairs[k + 1]
            if yb - ya < min_gap:
                mid  = (ya + yb) / 2
                pairs[k]     = (ia, mid - min_gap / 2)
                pairs[k + 1] = (ib, mid + min_gap / 2)
                moved = True
        if not moved:
            break
    result = [0] * len(ys)
    for idx, y in pairs:
        result[idx] = y
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 4 — Category-level EN-KO Score Gap (Qwen-32B judge)
# ═══════════════════════════════════════════════════════════════════════════════

def fig4_category_gap(cat_df):
    sub = cat_df[cat_df["judge"] == "qwen_32B"].copy()
    sub = sub.sort_values("delta")   # most negative → top of chart

    cats   = [CAT_DISPLAY.get(c, c) for c in sub["category"]]
    deltas = sub["delta"].tolist()
    colors = [C_CODE if c == "coding" else C_EN for c in sub["category"]]

    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    ax.set_axisbelow(True)
    ax.grid(axis="x", zorder=0)

    bars = ax.barh(cats, deltas, color=colors, height=0.58, zorder=3,
                   edgecolor="white", linewidth=0.3)

    # Value labels
    for bar, v, c in zip(bars, deltas, sub["category"]):
        is_code = (c == "coding")
        text_x  = v + 0.04 if is_code else v - 0.04
        ha      = "left"   if is_code else "right"
        col     = C_CODE   if is_code else "white"
        ax.text(text_x, bar.get_y() + bar.get_height() / 2,
                f"{v:.2f}", ha=ha, va="center",
                fontsize=8.5, color=col, fontweight="bold")

    ax.axvline(0, color="#333333", lw=0.9, zorder=2)
    ax.set_xlabel("Score Gap  (Korean − English,  Qwen-32B judge)", labelpad=6)
    ax.set_xlim(-2.5, 0.45)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(0.5))
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.yaxis.grid(False)

    patches = [
        mpatches.Patch(color=C_EN,   label="Other categories"),
        mpatches.Patch(color=C_CODE, label="Coding (smallest gap)"),
    ]
    ax.legend(handles=patches, loc="lower right", frameon=True)

    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"fig4_category_gap.{ext}")
    plt.close(fig)
    print("✓  fig4_category_gap")


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    secs = load_comparison_csv()

    incon_key = next(k for k in secs if "Inconsistency" in k)
    cat_key   = next(k for k in secs if "Score Gap" in k or "카테고리" in k)

    incon_df = secs[incon_key]
    cat_df   = secs[cat_key]

    fig1_inconsistency(incon_df)
    fig2_position_breakdown(incon_df)
    fig3_score_slope()
    fig4_category_gap(cat_df)

    print(f"\n✓  All figures → {OUT}")
