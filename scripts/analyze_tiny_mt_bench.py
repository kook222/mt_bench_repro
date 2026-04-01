#!/usr/bin/env python3
"""
scripts/analyze_tiny_mt_bench.py

tinyMT-Bench: 최소 변별 문항 세트 발굴
=========================================
연구 질문:
  변별도 상위 N개 문항만으로 80문항 전체와 동일한 모델 순위를 얻을 수 있는가?
  "변별도 기반 선택" vs "랜덤 선택" 중 어느 쪽이 더 빠르게 순위에 수렴하는가?

방법:
  - 80문항 기준 모델 순위를 baseline으로 설정
  - for N in [5, 10, 15, 20, 25, 30, 40, 60]:
      방법 A (Random):  랜덤 N개 문항 → 30회 반복 → Spearman ρ 평균/min/max
      방법 B (Top-Disc): 변별도(std) 상위 N개 문항 → 고정 → Spearman ρ
  - 두 방법 비교: 동일 ρ를 달성하는 데 필요한 최소 N 차이

출력:
  data/results_tiny_mt_bench.csv   — N별 Random/TopDisc ρ 비교 테이블
  figures/fig9_tiny_mt_bench.png   — 비교 figure (3-panel)

Usage:
    export PYTHONPATH=src
    python3 scripts/analyze_tiny_mt_bench.py
"""

from __future__ import annotations

import csv
import random
import statistics
import sys
from pathlib import Path
from collections import defaultdict

# ── 경로 ──────────────────────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_DIR = _SCRIPT_DIR.parent
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
DISC_CSV   = _PROJECT_DIR / "data" / "results_discriminability.csv"
GRADE_DIR  = _PROJECT_DIR / "data" / "judgments" / "single_grade"
OUTPUT_CSV = _PROJECT_DIR / "data" / "results_tiny_mt_bench.csv"

MODELS = [
    "Phi-3.5-mini-Instruct",
    "gemma-2-9b-it",
    "Yi-1.5-9B-Chat",
    "Mistral-7B-Instruct-v0.3",
    "SOLAR-10.7B-Instruct",
    "Zephyr-7B-beta",
]
N_SIZES  = [5, 10, 15, 20, 25, 30, 40, 60, 80]
N_TRIALS = 200   # 랜덤 서브샘플 반복 횟수 (많을수록 분산 추정 정확)
SEED     = 42


# ── 유틸 ──────────────────────────────────────────────────────────────────────
def spearman_rho(a: dict[str, float], b: dict[str, float]) -> float | None:
    common = sorted(set(a) & set(b))
    if len(common) < 2:
        return None

    def ranks(vals):
        idx = sorted(range(len(vals)), key=lambda i: vals[i])
        r = [0.0] * len(vals)
        for rank, i in enumerate(idx):
            r[i] = float(rank + 1)
        return r

    av = [a[m] for m in common]
    bv = [b[m] for m in common]
    ra, rb = ranks(av), ranks(bv)
    n = len(ra)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    sa  = sum((r - ma) ** 2 for r in ra) ** 0.5
    sb  = sum((r - mb) ** 2 for r in rb) ** 0.5
    if sa == 0 or sb == 0:
        return None
    return cov / (sa * sb)


# ── 데이터 로드 ────────────────────────────────────────────────────────────────
def load_disc_ranking() -> list[int]:
    """결과 CSV에서 disc_rank 순서대로 question_id 반환."""
    rows = []
    with open(DISC_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append((int(row["disc_rank"]), int(row["question_id"])))
    rows.sort()
    return [qid for _, qid in rows]


def load_per_question_model_scores() -> dict[int, dict[str, float]]:
    """question_id → {model: avg(turn1, turn2)} 딕셔너리 반환."""
    raw: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for model in MODELS:
        path = GRADE_DIR / f"{model}.jsonl"
        if not path.exists():
            continue
        import json
        for line in path.open():
            j = json.loads(line)
            qid = j["question_id"]
            if j["score_turn1"] >= 0:
                raw[qid][model].append(j["score_turn1"])
            if j["score_turn2"] >= 0:
                raw[qid][model].append(j["score_turn2"])

    result: dict[int, dict[str, float]] = {}
    for qid, mdict in raw.items():
        avgs = {m: sum(v) / len(v) for m, v in mdict.items() if v}
        if len(avgs) == len(MODELS):   # 모든 모델 점수 있는 문항만
            result[qid] = avgs
    return result


def model_scores_from_questions(
    q_model_scores: dict[int, dict[str, float]],
    qids: list[int],
) -> dict[str, float]:
    """주어진 문항 subset의 모델별 평균 점수."""
    acc: dict[str, list[float]] = defaultdict(list)
    for qid in qids:
        if qid in q_model_scores:
            for model, score in q_model_scores[qid].items():
                acc[model].append(score)
    return {m: sum(v) / len(v) for m, v in acc.items() if v}


# ── 분석 ──────────────────────────────────────────────────────────────────────
def run_analysis(
    q_model_scores: dict[int, dict[str, float]],
    disc_qids: list[int],
) -> list[dict]:
    all_qids  = list(q_model_scores.keys())
    full_scores = model_scores_from_questions(q_model_scores, all_qids)
    rng = random.Random(SEED)

    rows = []
    print(f"\n  {'N':>4}  {'Random μρ':>10}  {'Random min':>10}  {'Random max':>10}  {'TopDisc ρ':>10}")
    print(f"  {'-'*55}")

    for n in N_SIZES:
        if n >= len(all_qids):
            rows.append({
                "n": n,
                "random_mean": 1.0, "random_min": 1.0, "random_max": 1.0,
                "topdisc_rho": 1.0,
            })
            print(f"  {n:>4}  {'1.000':>10}  {'1.000':>10}  {'1.000':>10}  {'1.000':>10}  (전체)")
            continue

        # ── 방법 A: Random ──────────────────────────────────────────────────
        rhos_rand = []
        for _ in range(N_TRIALS):
            sampled = rng.sample(all_qids, n)
            sub_scores = model_scores_from_questions(q_model_scores, sampled)
            rho = spearman_rho(sub_scores, full_scores)
            if rho is not None:
                rhos_rand.append(rho)

        rand_mean = statistics.mean(rhos_rand) if rhos_rand else float("nan")
        rand_min  = min(rhos_rand)             if rhos_rand else float("nan")
        rand_max  = max(rhos_rand)             if rhos_rand else float("nan")

        # ── 방법 B: Top-N Discriminative ────────────────────────────────────
        top_n_qids   = [qid for qid in disc_qids[:n] if qid in q_model_scores]
        topdisc_scores = model_scores_from_questions(q_model_scores, top_n_qids)
        rho_disc     = spearman_rho(topdisc_scores, full_scores)

        rows.append({
            "n": n,
            "random_mean": rand_mean,
            "random_min":  rand_min,
            "random_max":  rand_max,
            "topdisc_rho": rho_disc if rho_disc is not None else float("nan"),
        })
        print(f"  {n:>4}  {rand_mean:>10.4f}  {rand_min:>10.4f}  {rand_max:>10.4f}  "
              f"{(rho_disc or float('nan')):>10.4f}")

    return rows


# ── 결과 출력 ─────────────────────────────────────────────────────────────────
def print_insight(rows: list[dict]) -> None:
    print("\n" + "=" * 65)
    print("  KEY FINDINGS")
    print("=" * 65)

    # Top-disc가 ρ≥0.95를 달성하는 최소 N
    disc_thresh = next((r["n"] for r in rows if r["topdisc_rho"] >= 0.95), None)
    rand_thresh = next((r["n"] for r in rows if r["random_mean"] >= 0.95), None)
    print(f"\n  ρ ≥ 0.95 달성 최소 문항 수:")
    print(f"    Top-Disc 선택: {disc_thresh}개")
    print(f"    Random   선택: {rand_thresh}개 (평균 기준)")

    if disc_thresh and rand_thresh:
        saving = rand_thresh - disc_thresh
        pct    = saving / rand_thresh * 100
        print(f"    → Top-Disc가 {saving}개 적은 문항으로 동일 신뢰도 달성 ({pct:.0f}% 절감)")

    # 각 N에서 이득
    print(f"\n  N별 TopDisc 이득 (TopDisc ρ − Random 평균 ρ):")
    for r in rows:
        if r["n"] in [10, 20, 30, 40]:
            gain = r["topdisc_rho"] - r["random_mean"]
            print(f"    N={r['n']:>2}: TopDisc={r['topdisc_rho']:.4f}  "
                  f"Random={r['random_mean']:.4f}  gain=+{gain:.4f}")

    # 80문항 대비 압축률
    if disc_thresh:
        print(f"\n  80문항 대비 {disc_thresh}개 문항으로 ρ≥0.95 → "
              f"{(1 - disc_thresh/80)*100:.0f}% 문항 절감")


# ── CSV 저장 ──────────────────────────────────────────────────────────────────
def save_csv(rows: list[dict]) -> None:
    fields = ["n", "random_mean", "random_min", "random_max", "topdisc_rho"]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: f"{v:.6f}" if isinstance(v, float) else v
                             for k, v in r.items()})
    print(f"\n  저장: {OUTPUT_CSV.name}")


# ── 시각화 ────────────────────────────────────────────────────────────────────
def make_figure(rows: list[dict], q_model_scores: dict, disc_qids: list[int]) -> None:
    ns          = [r["n"]            for r in rows]
    rand_means  = [r["random_mean"]  for r in rows]
    rand_mins   = [r["random_min"]   for r in rows]
    rand_maxs   = [r["random_max"]   for r in rows]
    disc_rhos   = [r["topdisc_rho"]  for r in rows]

    fig, axes = plt.subplots(1, 3, figsize=(16, 5.5))
    fig.patch.set_facecolor("white")

    # ── (A) 핵심: Random vs TopDisc Spearman ρ ────────────────────────────────
    ax = axes[0]
    ax.fill_between(ns, rand_mins, rand_maxs, alpha=0.15, color="#1565C0",
                    label="Random: min–max range")
    ax.plot(ns, rand_means, "o--", color="#1565C0", linewidth=2.2,
            markersize=8, markerfacecolor="white", markeredgewidth=2.2,
            label="Random: mean ρ", zorder=5)
    ax.plot(ns, disc_rhos, "s-", color="#E53935", linewidth=2.5,
            markersize=8, markerfacecolor="white", markeredgewidth=2.5,
            label="Top-Disc: ρ", zorder=6)

    ax.axhline(0.95, color="gray", linestyle=":", linewidth=1.5,
               alpha=0.8, label="ρ = 0.95 (stable)")

    # ρ=0.95 달성 지점 표시
    for rhos, color, label in [(disc_rhos, "#E53935", "TopDisc"), (rand_means, "#1565C0", "Random")]:
        for i, (n, r) in enumerate(zip(ns, rhos)):
            if r >= 0.95:
                ax.axvline(n, color=color, linestyle="--", linewidth=1.2, alpha=0.5)
                ax.annotate(f"{label}\nN={n}", xy=(n, 0.95),
                            xytext=(n + 1, 0.88 if color == "#E53935" else 0.82),
                            fontsize=9, color=color, fontweight="bold",
                            arrowprops=dict(arrowstyle="-", color=color, lw=0.8))
                break

    ax.set_xlabel("Number of Questions (N)", fontsize=11)
    ax.set_ylabel("Spearman ρ vs. Full 80-Question Ranking", fontsize=11)
    ax.set_title("(A) Random vs. Top-Discriminative Selection\nSpearman ρ Comparison", fontsize=12, fontweight="bold")
    ax.set_xlim(0, 85)
    ax.set_ylim(0.3, 1.08)
    ax.set_xticks(ns)
    ax.legend(fontsize=9.5, framealpha=0.85, loc="lower right")
    ax.grid(True, linestyle="--", alpha=0.35)
    ax.set_axisbelow(True)

    # ── (B) 이득 (TopDisc − Random) ───────────────────────────────────────────
    ax2 = axes[1]
    gains = [d - r for d, r in zip(disc_rhos, rand_means)]
    bar_colors = ["#E53935" if g > 0 else "#90A4AE" for g in gains]
    bars = ax2.bar(range(len(ns)), gains, color=bar_colors, alpha=0.88,
                   edgecolor="white", width=0.6)

    ax2.axhline(0, color="black", linewidth=0.8)
    ax2.set_xticks(range(len(ns)))
    ax2.set_xticklabels([str(n) for n in ns], fontsize=11)
    ax2.set_xlabel("Number of Questions (N)", fontsize=11)
    ax2.set_ylabel("ρ Gain (TopDisc − Random mean)", fontsize=11)
    ax2.set_title("(B) Advantage of Top-Disc Selection\n(positive = TopDisc outperforms Random)", fontsize=12, fontweight="bold")
    ax2.grid(True, axis="y", linestyle="--", alpha=0.35)
    ax2.set_axisbelow(True)

    for bar, val in zip(bars, gains):
        label = f"+{val:.3f}" if val >= 0 else f"{val:.3f}"
        ax2.text(bar.get_x() + bar.get_width()/2,
                 val + (0.003 if val >= 0 else -0.008),
                 label, ha="center", va="bottom" if val >= 0 else "top",
                 fontsize=9.5, fontweight="bold", color="#333")

    # ── (C) 모델 순위 비교: 80문항 vs TopDisc-20 vs Random-20 ────────────────
    ax3 = axes[2]

    full_scores  = model_scores_from_questions(q_model_scores, list(q_model_scores.keys()))
    top20_qids   = [qid for qid in disc_qids[:20] if qid in q_model_scores]
    top20_scores = model_scores_from_questions(q_model_scores, top20_qids)

    rng = random.Random(SEED)
    all_qids = list(q_model_scores.keys())
    rand20_qids   = rng.sample(all_qids, 20)
    rand20_scores = model_scores_from_questions(q_model_scores, rand20_qids)

    models_by_full = sorted(full_scores, key=lambda m: full_scores[m], reverse=True)

    x = np.arange(len(models_by_full))
    w = 0.25
    short_names = [m.replace("-Instruct", "").replace("-beta", "").replace("-Chat", "")
                   .replace("Phi-3.5-mini", "Phi-3.5").replace("gemma-2-9b-it", "gemma-2-9b")
                   for m in models_by_full]

    b1 = ax3.bar(x - w, [full_scores[m]  for m in models_by_full], w,
                 label="Full 80 questions", color="#455A64", alpha=0.88, edgecolor="white")
    b2 = ax3.bar(x,     [top20_scores.get(m, 0) for m in models_by_full], w,
                 label="TopDisc top-20", color="#E53935", alpha=0.88, edgecolor="white")
    b3 = ax3.bar(x + w, [rand20_scores.get(m, 0) for m in models_by_full], w,
                 label="Random 20 (1 trial)", color="#1565C0", alpha=0.88, edgecolor="white")

    ax3.set_xticks(x)
    ax3.set_xticklabels(short_names, rotation=20, ha="right", fontsize=9.5)
    ax3.set_ylabel("MT-Bench Score", fontsize=11)
    ax3.set_ylim(4.0, 10.0)
    ax3.set_title("(C) Model Ranking Comparison (N=20)\nFull-80 vs TopDisc-20 vs Random-20",
                  fontsize=12, fontweight="bold")
    ax3.legend(fontsize=9.5, framealpha=0.85)
    ax3.grid(True, axis="y", linestyle="--", alpha=0.35)
    ax3.set_axisbelow(True)

    rho_disc20 = spearman_rho(top20_scores, full_scores)
    rho_rand20 = spearman_rho(rand20_scores, full_scores)
    ax3.text(0.02, 0.04,
             f"TopDisc-20: ρ={rho_disc20:.3f}\nRandom-20:  ρ={rho_rand20:.3f}",
             transform=ax3.transAxes, fontsize=10, fontweight="bold",
             color="#333", verticalalignment="bottom",
             bbox=dict(boxstyle="round,pad=0.4", facecolor="white", alpha=0.85))

    fig.suptitle(
        "tinyMT-Bench: Minimum Discriminative Question Set\n"
        "Discriminability-Based Selection vs. Random Selection",
        fontsize=14, fontweight="bold", y=1.02,
    )
    plt.tight_layout()
    out = FIGURES_DIR / "fig9_tiny_mt_bench.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"  저장: {out.name}")


# ── main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    print("=" * 65)
    print("  tinyMT-Bench Analysis")
    print(f"  N_SIZES  = {N_SIZES}")
    print(f"  N_TRIALS = {N_TRIALS} (Random 반복 횟수)")
    print("=" * 65)

    disc_qids      = load_disc_ranking()
    q_model_scores = load_per_question_model_scores()

    print(f"\n  문항 수 (전 모델 점수 보유): {len(q_model_scores)}")
    print(f"  변별도 순위 상위 10개 QID: {disc_qids[:10]}")

    rows = run_analysis(q_model_scores, disc_qids)
    print_insight(rows)
    save_csv(rows)
    make_figure(rows, q_model_scores, disc_qids)

    print("\n" + "=" * 65)
    print("  완료.")
    print("=" * 65)


if __name__ == "__main__":
    main()
