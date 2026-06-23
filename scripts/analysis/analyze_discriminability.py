#!/usr/bin/env python3
"""
scripts/analysis/analyze_discriminability.py

Discriminability-Based Gap Analysis
====================================
Research question:
  If we define "hard" questions by **inter-model score variance** (std across models)
  instead of fixed category labels (math/reasoning/coding), what pattern emerges?

Methodology:
  1. For each of the 80 MT-Bench questions (2 turns each), compute the std of
     per-turn average scores across all 6 evaluated models.
  2. Rank questions by std → "discriminative" (high std) vs. "easy" (low std).
  3. Compare this data-driven classification with the paper's category-based
     hard/easy split.
  4. Measure: what fraction of the top-N discriminative questions come from
     each category?  Does category explain discriminability?

Outputs:
  data/results_discriminability.csv   — per-question std, category, rank
  figures/fig8_discriminability.png   — 4-panel publication figure

Usage:
    export PYTHONPATH=src
    python3 scripts/analysis/analyze_discriminability.py
"""

from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

# ── 경로 ──────────────────────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_DIR = _SCRIPT_DIR.parents[1]
if str(_PROJECT_DIR / "src") not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR / "src"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

FIGURES_DIR = _PROJECT_DIR / "figures"
FIGURES_DIR.mkdir(exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.35,
    "grid.linestyle": "--",
    "figure.dpi": 150,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
    "savefig.facecolor": "white",
})

# ── 상수 ──────────────────────────────────────────────────────────────────────
GRADE_DIR  = _PROJECT_DIR / "data" / "judgments_phase3" / "judge_32B" / "single_grade"
Q_FILE     = _PROJECT_DIR / "data" / "mt_bench_questions.jsonl"
OUTPUT_CSV = _PROJECT_DIR / "data" / "results_discriminability.csv"

# Phase 3 subject 모델 7개 (Qwen 계열 제외 — judge 역할)
MODELS = [
    "Phi-3.5-mini-Instruct",
    "gemma-2-9b-it",
    "Yi-1.5-9B-Chat",
    "Mistral-7B-Instruct-v0.3",
    "SOLAR-10.7B-Instruct",
    "Zephyr-7B-beta",
    "Llama-3.1-8B-Instruct",
]

HARD_CATS = {"math", "reasoning", "coding"}
EASY_CATS = {"writing", "roleplay", "extraction", "stem", "humanities"}

CAT_COLORS = {
    "writing":    "#42A5F5",
    "roleplay":   "#66BB6A",
    "extraction": "#FFA726",
    "reasoning":  "#EF5350",
    "math":       "#AB47BC",
    "coding":     "#26C6DA",
    "stem":       "#8D6E63",
    "humanities": "#78909C",
}


# ── 데이터 로드 ────────────────────────────────────────────────────────────────
def load_question_categories() -> dict[int, str]:
    cats: dict[int, str] = {}
    for line in Q_FILE.open():
        q = json.loads(line)
        cats[q["question_id"]] = q["category"]
    return cats


def load_per_question_model_scores() -> dict[int, dict[str, float]]:
    """Returns {question_id: {model: avg_of_turn1_turn2}}."""
    q_model_scores: dict[int, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for model in MODELS:
        path = GRADE_DIR / f"{model}.jsonl"
        if not path.exists():
            print(f"  [WARN] missing: {path.name}")
            continue
        for line in path.open():
            j = json.loads(line)
            qid = j["question_id"]
            if j["score_turn1"] >= 0:
                q_model_scores[qid][model].append(j["score_turn1"])
            if j["score_turn2"] >= 0:
                q_model_scores[qid][model].append(j["score_turn2"])

    result: dict[int, dict[str, float]] = {}
    for qid, mdict in q_model_scores.items():
        avgs = {m: sum(v) / len(v) for m, v in mdict.items() if v}
        if len(avgs) >= 2:
            result[qid] = avgs
    return result


# ── 분석 ──────────────────────────────────────────────────────────────────────
def compute_discriminability(
    q_model_scores: dict[int, dict[str, float]],
    q_cats: dict[int, str],
) -> list[dict]:
    rows = []
    for qid, mavg in q_model_scores.items():
        vals = list(mavg.values())
        std  = statistics.stdev(vals)
        mean = sum(vals) / len(vals)
        cat  = q_cats.get(qid, "unknown")
        rows.append({
            "question_id": qid,
            "category": cat,
            "label_hard": cat in HARD_CATS,
            "mean_score": mean,
            "std_score": std,
            **{f"score_{m.replace('-', '_')}": mavg.get(m, float("nan")) for m in MODELS},
        })
    rows.sort(key=lambda r: r["std_score"], reverse=True)
    for rank, row in enumerate(rows, 1):
        row["disc_rank"] = rank
    return rows


def category_discriminability_stats(rows: list[dict]) -> dict[str, dict]:
    """Per-category mean/std of the per-question std values."""
    cat_stds: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        cat_stds[r["category"]].append(r["std_score"])
    stats: dict[str, dict] = {}
    for cat, stds in cat_stds.items():
        stats[cat] = {
            "mean_std": sum(stds) / len(stds),
            "max_std":  max(stds),
            "min_std":  min(stds),
            "n": len(stds),
        }
    return stats


# ── 시각화 ────────────────────────────────────────────────────────────────────
def make_figure(rows: list[dict], cat_stats: dict[str, dict]) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(14, 11))
    fig.patch.set_facecolor("white")

    # ── (A) Per-question std, sorted — scatter colored by category ────────────
    ax_a = axes[0, 0]
    ax_a.set_title("(A) Per-Question Discriminability\n(std of model scores, sorted)",
                   fontsize=12, fontweight="bold")

    # plot in rank order (already sorted desc by std)
    xs = list(range(1, len(rows) + 1))
    ys = [r["std_score"] for r in rows]
    cs = [CAT_COLORS[r["category"]] for r in rows]

    ax_a.scatter(xs, ys, c=cs, s=48, alpha=0.85, edgecolors="white", linewidths=0.4, zorder=3)

    # top-20 threshold line
    top20_threshold = rows[19]["std_score"] if len(rows) >= 20 else 0
    ax_a.axvline(20, color="#D32F2F", linestyle="--", linewidth=1.5,
                 label=f"Top-20 cutoff (std ≥ {top20_threshold:.2f})", zorder=4)

    ax_a.set_xlabel("Question rank (by discriminability)", fontsize=11)
    ax_a.set_ylabel("Std of model scores", fontsize=11)
    ax_a.set_xlim(0, len(rows) + 1)
    ax_a.set_ylim(-0.1, max(ys) + 0.3)
    ax_a.grid(True, linestyle="--", alpha=0.35)
    ax_a.set_axisbelow(True)

    handles = [mpatches.Patch(color=CAT_COLORS[c], label=c) for c in CAT_COLORS]
    ax_a.legend(handles=handles, fontsize=8.5, ncol=2, framealpha=0.85,
                loc="upper right")

    # ── (B) Category composition of top-N discriminative questions ───────────
    ax_b = axes[0, 1]
    ax_b.set_title("(B) Category Composition of Top-N Discriminative Questions\n"
                   "(data-driven hard vs. label-based hard)",
                   fontsize=12, fontweight="bold")

    top_ns = [10, 20, 30, 40, 50]
    cats_ordered = sorted(CAT_COLORS.keys())
    bottom = np.zeros(len(top_ns))

    for cat in cats_ordered:
        fracs = []
        for n in top_ns:
            top_n_rows = rows[:n]
            frac = sum(1 for r in top_n_rows if r["category"] == cat) / n * 100
            fracs.append(frac)
        bars = ax_b.bar(range(len(top_ns)), fracs, bottom=bottom,
                        color=CAT_COLORS[cat], label=cat, alpha=0.9, width=0.65)
        bottom += np.array(fracs)

    ax_b.set_xticks(range(len(top_ns)))
    ax_b.set_xticklabels([f"Top-{n}" for n in top_ns], fontsize=11)
    ax_b.set_ylabel("Percentage (%)", fontsize=11)
    ax_b.set_ylim(0, 105)
    ax_b.axhline(100/8, color="black", linestyle=":", linewidth=1.2,
                 alpha=0.5, label="Uniform (12.5%)")
    ax_b.legend(fontsize=9, framealpha=0.85, loc="upper right", ncol=2)
    ax_b.grid(True, axis="y", linestyle="--", alpha=0.35)
    ax_b.set_axisbelow(True)

    # ── (C) Per-category mean discriminability ────────────────────────────────
    ax_c = axes[1, 0]
    ax_c.set_title("(C) Mean Discriminability per Category\n"
                   "(higher = more spread between models)",
                   fontsize=12, fontweight="bold")

    cats_sorted = sorted(cat_stats.keys(), key=lambda c: cat_stats[c]["mean_std"], reverse=True)
    x_c = range(len(cats_sorted))
    bar_colors_c = [CAT_COLORS[c] for c in cats_sorted]
    mean_stds = [cat_stats[c]["mean_std"] for c in cats_sorted]
    max_stds  = [cat_stats[c]["max_std"]  for c in cats_sorted]
    min_stds  = [cat_stats[c]["min_std"]  for c in cats_sorted]

    bars_c = ax_c.bar(x_c, mean_stds, color=bar_colors_c, alpha=0.9,
                      edgecolor="white", width=0.6)
    # error bars showing min-max range
    ax_c.errorbar(x_c, mean_stds,
                  yerr=[
                      [m - lo for m, lo in zip(mean_stds, min_stds)],
                      [hi - m  for m, hi  in zip(mean_stds, max_stds)],
                  ],
                  fmt="none", color="#333", capsize=5, linewidth=1.5, zorder=5)

    for bar, val in zip(bars_c, mean_stds):
        ax_c.text(bar.get_x() + bar.get_width()/2, val + 0.04,
                  f"{val:.2f}", ha="center", va="bottom",
                  fontsize=10, fontweight="bold", color="#333")

    # Shade hard categories background
    hard_xs = [i for i, c in enumerate(cats_sorted) if c in HARD_CATS]
    for hx in hard_xs:
        ax_c.axvspan(hx - 0.4, hx + 0.4, alpha=0.08, color="#D32F2F")

    ax_c.set_xticks(x_c)
    ax_c.set_xticklabels(cats_sorted, fontsize=11)
    ax_c.set_ylabel("Mean std of model scores", fontsize=11)
    ax_c.set_ylim(0, max(max_stds) + 0.5)
    ax_c.grid(True, axis="y", linestyle="--", alpha=0.35)
    ax_c.set_axisbelow(True)
    hard_patch = mpatches.Patch(color="#D32F2F", alpha=0.15, label="Paper's hard categories")
    ax_c.legend(handles=[hard_patch], fontsize=10, framealpha=0.85)

    # ── (D) Score spread vs. mean score (difficulty vs. discriminability) ─────
    ax_d = axes[1, 1]
    ax_d.set_title("(D) Mean Score vs. Discriminability\n"
                   "(each dot = one question)",
                   fontsize=12, fontweight="bold")

    xs_d = [r["mean_score"] for r in rows]
    ys_d = [r["std_score"]  for r in rows]
    cs_d = [CAT_COLORS[r["category"]] for r in rows]

    ax_d.scatter(xs_d, ys_d, c=cs_d, s=52, alpha=0.80,
                 edgecolors="white", linewidths=0.4, zorder=3)

    # Annotate top-5 most discriminative
    for r in rows[:5]:
        ax_d.annotate(
            f"q{r['question_id']}\n({r['category']})",
            xy=(r["mean_score"], r["std_score"]),
            xytext=(r["mean_score"] - 0.6, r["std_score"] + 0.12),
            fontsize=8, color="#333",
            arrowprops=dict(arrowstyle="-", color="#999", lw=0.8),
        )

    ax_d.set_xlabel("Mean score across models", fontsize=11)
    ax_d.set_ylabel("Std of model scores (discriminability)", fontsize=11)
    ax_d.grid(True, linestyle="--", alpha=0.35)
    ax_d.set_axisbelow(True)

    handles_d = [mpatches.Patch(color=CAT_COLORS[c], label=c) for c in CAT_COLORS]
    ax_d.legend(handles=handles_d, fontsize=8.5, ncol=2, framealpha=0.85,
                loc="upper left")

    fig.suptitle(
        "Discriminability-Based Gap Analysis\n"
        "Redefining 'hard' by inter-model score variance instead of fixed category labels",
        fontsize=14, fontweight="bold", y=1.01,
    )

    plt.tight_layout()
    out = FIGURES_DIR / "fig8_discriminability.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ── 결과 출력 ─────────────────────────────────────────────────────────────────
def print_summary(rows: list[dict], cat_stats: dict[str, dict]) -> None:
    print("\n" + "=" * 70)
    print("  DISCRIMINABILITY ANALYSIS — SUMMARY")
    print("=" * 70)

    print("\n  Top-20 Most Discriminative Questions:")
    print(f"  {'Rank':>4}  {'QID':>4}  {'Category':>12}  {'Std':>6}  {'Mean':>6}  {'Paper Hard?':>11}")
    print(f"  {'-'*55}")
    for r in rows[:20]:
        is_hard = "✅ hard" if r["label_hard"] else "— easy"
        print(f"  {r['disc_rank']:>4}  {r['question_id']:>4}  "
              f"{r['category']:>12}  {r['std_score']:>6.3f}  {r['mean_score']:>6.2f}  {is_hard:>11}")

    print("\n  Per-Category Mean Discriminability (sorted):")
    print(f"  {'Category':>12}  {'Mean Std':>8}  {'Max Std':>8}  {'Min Std':>8}  {'Paper Label':>12}")
    print(f"  {'-'*58}")
    for cat, s in sorted(cat_stats.items(), key=lambda x: x[1]["mean_std"], reverse=True):
        label = "HARD" if cat in HARD_CATS else "easy"
        print(f"  {cat:>12}  {s['mean_std']:>8.3f}  {s['max_std']:>8.3f}  "
              f"{s['min_std']:>8.3f}  {label:>12}")

    # Top-20 category distribution
    top20_cats: dict[str, int] = defaultdict(int)
    for r in rows[:20]:
        top20_cats[r["category"]] += 1
    total_hard_in_top20 = sum(v for k, v in top20_cats.items() if k in HARD_CATS)
    print(f"\n  Top-20 Category Distribution:")
    for cat in sorted(top20_cats, key=lambda c: top20_cats[c], reverse=True):
        bar = "█" * top20_cats[cat]
        label = " ← hard" if cat in HARD_CATS else ""
        print(f"    {cat:>12}: {top20_cats[cat]:>2}  {bar}{label}")
    pct = total_hard_in_top20 / 20 * 100
    print(f"\n  Hard categories in top-20: {total_hard_in_top20}/20 ({pct:.0f}%)")
    print(f"  (Expected if uniform: {3/8*20:.1f}/20 = {3/8*100:.1f}%)")

    # Surprise: extraction in top?
    extraction_in_top20 = top20_cats.get("extraction", 0)
    roleplay_in_top20   = top20_cats.get("roleplay", 0)
    print(f"\n  Surprises:")
    print(f"    extraction in top-20: {extraction_in_top20} "
          f"({'OVER-represented' if extraction_in_top20 > 2 else 'as expected'})")
    print(f"    roleplay   in top-20: {roleplay_in_top20} "
          f"({'OVER-represented' if roleplay_in_top20 > 2 else 'as expected'})")


# ── CSV 저장 ──────────────────────────────────────────────────────────────────
def save_csv(rows: list[dict]) -> None:
    fields = ["disc_rank", "question_id", "category", "label_hard",
              "mean_score", "std_score"] + [f"score_{m.replace('-', '_')}" for m in MODELS]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({
                k: (f"{v:.4f}" if isinstance(v, float) and not isinstance(v, bool) else v)
                for k, v in r.items()
            })
    print(f"\n  Saved: {OUTPUT_CSV.name}")


# ── main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    print("=" * 70)
    print("  Discriminability-Based Gap Analysis")
    print("=" * 70)

    q_cats = load_question_categories()
    q_model_scores = load_per_question_model_scores()

    print(f"\n  Questions loaded : {len(q_model_scores)}")
    print(f"  Models           : {len(MODELS)}")

    rows = compute_discriminability(q_model_scores, q_cats)
    cat_stats = category_discriminability_stats(rows)

    print_summary(rows, cat_stats)
    save_csv(rows)
    make_figure(rows, cat_stats)

    print("\n" + "=" * 70)
    print("  Done.")
    print("=" * 70)


if __name__ == "__main__":
    main()
