"""
Judge 선택에 따른 랭킹 민감도 심층 분석.

생성 figure:
  fig_category_tau.png     — 카테고리별 평균 Kendall τ distance (judge 불안정 위치)
  fig_model_sensitivity.png — 모델별 judge 간 점수 std (judge에 민감한 모델)
  fig_reference_penalty.png — Standard vs Reference-guided 점수 차이 (judge별)
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import kendalltau

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_DIR / "data"
FIG_DIR = PROJECT_DIR / "figures"
FIG_DIR.mkdir(exist_ok=True)

JUDGE_FILES = {
    "Qwen-7B":     DATA_DIR / "results_phase3_judge_7B.csv",
    "Qwen-14B":    DATA_DIR / "results_phase3_judge_14B.csv",
    "Qwen-32B":    DATA_DIR / "results_phase3_judge_32B.csv",
    "GPT-4o-mini": DATA_DIR / "results_phase5_gpt4omini.csv",
}
REF_FILES = {
    "Qwen-7B":     DATA_DIR / "results_phase3_judge_7B_reference.csv",
    "Qwen-14B":    DATA_DIR / "results_phase3_judge_14B_reference.csv",
    "Qwen-32B":    DATA_DIR / "results_phase3_judge_32B_reference.csv",
    "GPT-4o-mini": DATA_DIR / "results_phase5_gpt4omini_reference.csv",
}
CATEGORIES = ["writing", "roleplay", "extraction", "reasoning",
              "math", "coding", "stem", "humanities"]
JUDGES = list(JUDGE_FILES.keys())


def load_csv(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def get_ranking(rows, col):
    rows = sorted(rows, key=lambda x: -float(x[col]))
    return {r["model"]: i + 1 for i, r in enumerate(rows)}


# ── Fig 1: 카테고리별 평균 Kendall τ distance ──────────────────────────────

def plot_category_tau():
    data = {j: load_csv(f) for j, f in JUDGE_FILES.items()}

    cat_avg_tau = []
    for cat in CATEGORIES:
        rankings = {j: get_ranking(data[j], cat) for j in JUDGES}
        models = [r["model"] for r in data[JUDGES[0]]]
        dists = []
        for i, j1 in enumerate(JUDGES):
            for j2 in JUDGES[i + 1:]:
                r1 = [rankings[j1][m] for m in models]
                r2 = [rankings[j2][m] for m in models]
                tau, _ = kendalltau(r1, r2)
                dists.append((1 - tau) / 2)
        cat_avg_tau.append(np.mean(dists))

    colors = ["#e74c3c" if v > 0.15 else "#f39c12" if v > 0.10 else "#27ae60"
              for v in cat_avg_tau]
    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.bar(CATEGORIES, cat_avg_tau, color=colors, edgecolor="white", linewidth=0.8)
    ax.axhline(np.mean(cat_avg_tau), color="gray", linestyle="--", linewidth=1,
               label=f"전체 평균 ({np.mean(cat_avg_tau):.3f})")
    for bar, val in zip(bars, cat_avg_tau):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.005,
                f"{val:.3f}", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.set_ylabel("평균 Kendall τ distance")
    ax.set_title("카테고리별 Judge 랭킹 불안정도 (평균 Kendall τ distance)", fontsize=12)
    ax.set_ylim(0, 0.45)
    ax.legend(fontsize=9)
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    out = FIG_DIR / "fig_category_tau.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[OK] {out}")


# ── Fig 2: 모델별 judge 간 점수 std ──────────────────────────────────────

def plot_model_sensitivity():
    data = {j: load_csv(f) for j, f in JUDGE_FILES.items()}
    models = [r["model"] for r in data[JUDGES[0]]]

    model_scores = {m: [float(data[j][[r["model"] for r in data[j]].index(m)]["overall"])
                        for j in JUDGES]
                    for m in models}
    model_std = {m: np.std(v) for m, v in model_scores.items()}
    model_range = {m: max(v) - min(v) for m, v in model_scores.items()}

    sorted_models = sorted(models, key=lambda m: -model_std[m])
    stds = [model_std[m] for m in sorted_models]
    ranges = [model_range[m] for m in sorted_models]
    short_names = [m.split("-")[0] + "-" + m.split("-")[1] if "-" in m else m
                   for m in sorted_models]
    short_names = [m.replace("-Instruct", "").replace("-Instruct", "").replace("v0.3", "")
                   for m in sorted_models]

    fig, ax = plt.subplots(figsize=(9, 4.5))
    x = np.arange(len(sorted_models))
    bars = ax.bar(x, stds, color="#3498db", alpha=0.8, label="점수 표준편차 (std)")
    ax2 = ax.twinx()
    ax2.plot(x, ranges, "o--", color="#e74c3c", linewidth=1.5, markersize=6,
             label="점수 범위 (max−min)")
    ax.set_xticks(x)
    ax.set_xticklabels(short_names, rotation=25, ha="right", fontsize=8.5)
    ax.set_ylabel("점수 표준편차 (std)")
    ax2.set_ylabel("점수 범위 (max − min)", color="#e74c3c")
    ax.set_title("모델별 Judge 민감도: judge에 따른 점수 변동", fontsize=12)
    for bar, val in zip(bars, stds):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.003,
                f"{val:.3f}", ha="center", va="bottom", fontsize=8.5)
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc="upper right", fontsize=9)
    plt.tight_layout()
    out = FIG_DIR / "fig_model_sensitivity.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[OK] {out}")


# ── Fig 3: Reference-guided 점수 하락 (judge별) ──────────────────────────

def plot_reference_penalty():
    std_data = {j: load_csv(f) for j, f in JUDGE_FILES.items()}
    ref_data = {j: load_csv(f) for j, f in REF_FILES.items()}

    def get_overall(rows):
        return {r["model"]: float(r["overall"]) for r in rows}

    # judge별 평균 점수 하락
    judge_avg_drop = {}
    judge_per_model = {}
    for j in JUDGES:
        std_scores = get_overall(std_data[j])
        ref_scores = get_overall(ref_data[j])
        common = set(std_scores) & set(ref_scores)
        drops = [ref_scores[m] - std_scores[m] for m in common]
        judge_avg_drop[j] = np.mean(drops)
        judge_per_model[j] = {m: ref_scores[m] - std_scores[m]
                               for m in common}

    models = sorted(judge_per_model[JUDGES[0]].keys(),
                    key=lambda m: np.mean([judge_per_model[j][m] for j in JUDGES]))

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))

    # 왼쪽: judge별 평균 하락
    ax = axes[0]
    colors = ["#9b59b6", "#2980b9", "#16a085", "#c0392b"]
    bars = ax.bar(JUDGES, [judge_avg_drop[j] for j in JUDGES],
                  color=colors, edgecolor="white")
    for bar, val in zip(bars, [judge_avg_drop[j] for j in JUDGES]):
        ax.text(bar.get_x() + bar.get_width() / 2, val - 0.05,
                f"{val:.2f}", ha="center", va="top", color="white",
                fontsize=10, fontweight="bold")
    ax.set_ylabel("평균 점수 하락 (reference − standard)")
    ax.set_title("Judge별 Reference-guided 평균 점수 하락", fontsize=11)
    ax.set_ylim(min(judge_avg_drop.values()) - 0.3, 0.1)

    # 오른쪽: 모델별 judge별 하락 grouped bar
    ax2 = axes[1]
    x = np.arange(len(models))
    width = 0.2
    for idx, (j, c) in enumerate(zip(JUDGES, colors)):
        drops = [judge_per_model[j][m] for m in models]
        ax2.bar(x + idx * width - 1.5 * width, drops, width,
                label=j, color=c, alpha=0.85)
    short = [m.replace("-Instruct", "").replace("-v0.3", "").replace("-beta", "")
             for m in models]
    ax2.set_xticks(x)
    ax2.set_xticklabels(short, rotation=25, ha="right", fontsize=8)
    ax2.axhline(0, color="black", linewidth=0.8)
    ax2.set_ylabel("점수 변화 (reference − standard)")
    ax2.set_title("모델별 Reference-guided 점수 변화", fontsize=11)
    ax2.legend(fontsize=8, loc="lower right")

    plt.suptitle("Reference 정답 제공 시 점수 하락: 큰 judge일수록 더 가혹",
                 fontsize=12, fontweight="bold")
    plt.tight_layout()
    out = FIG_DIR / "fig_reference_penalty.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[OK] {out}")


if __name__ == "__main__":
    os.chdir(PROJECT_DIR)
    print("=== Judge 민감도 분석 ===")
    plot_category_tau()
    plot_model_sensitivity()
    plot_reference_penalty()
    print("\n완료. figures/ 디렉토리 확인.")
