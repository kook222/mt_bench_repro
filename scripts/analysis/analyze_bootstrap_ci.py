"""
Cross-Judge Spearman ρ Bootstrap Confidence Interval

방법:
  - Phase 3 single_grade 데이터에서 문항(80개) 단위로 bootstrap 리샘플링
  - 각 bootstrap 샘플에서 모델별 평균 점수 계산 → 7개 모델 순위
  - 두 judge 간 Spearman ρ 계산 → 10,000회 반복
  - 2.5th / 97.5th 백분위 → 95% CI

출력:
  data/results_bootstrap_ci.csv
  figures/fig14_bootstrap_ci.png
"""

import json
import random
from pathlib import Path
from collections import defaultdict
import csv
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT     = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
FIG_DIR  = ROOT / "figures"
FIG_DIR.mkdir(exist_ok=True)

PHASE3_SINGLE = {
    "7B":  DATA_DIR / "judgments_phase3" / "judge_7B"  / "single_grade",
    "14B": DATA_DIR / "judgments_phase3" / "judge_14B" / "single_grade",
    "32B": DATA_DIR / "judgments_phase3" / "judge_32B" / "single_grade",
}

N_BOOTSTRAP = 10_000
SEED        = 42


# ── 데이터 로드 ───────────────────────────────────────────────────────────────
def load_single_grade(judge_dir: Path) -> dict:
    """
    Returns:
        {model_id: {question_id: avg_score}}
    """
    data = defaultdict(dict)
    for fpath in sorted(judge_dir.glob("*.jsonl")):
        model_id = fpath.stem
        with open(fpath) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                t1 = r.get("score_turn1", -1)
                t2 = r.get("score_turn2", -1)
                if t1 < 0 or t2 < 0:
                    continue
                qid = r["question_id"]
                data[model_id][qid] = (t1 + t2) / 2
    return dict(data)


# ── Spearman ρ ────────────────────────────────────────────────────────────────
def spearman_rho(scores_a: dict, scores_b: dict) -> float:
    """두 모델 점수 dict {model: score}의 Spearman ρ."""
    models = sorted(set(scores_a.keys()) & set(scores_b.keys()))
    if len(models) < 2:
        return float("nan")

    def rank(d, keys):
        sorted_keys = sorted(keys, key=lambda m: d[m], reverse=True)
        return {m: i + 1 for i, m in enumerate(sorted_keys)}

    ra = rank(scores_a, models)
    rb = rank(scores_b, models)
    n  = len(models)
    d2 = sum((ra[m] - rb[m]) ** 2 for m in models)
    return 1 - 6 * d2 / (n * (n ** 2 - 1))


# ── Bootstrap ─────────────────────────────────────────────────────────────────
def bootstrap_rho(data_a: dict, data_b: dict, n_iter: int, seed: int) -> list[float]:
    """
    data_a, data_b: {model_id: {question_id: score}}
    문항 단위로 bootstrap → 모델별 평균 → Spearman ρ
    """
    models  = sorted(set(data_a.keys()) & set(data_b.keys()))
    all_qids = sorted(set.union(*[set(data_a[m].keys()) for m in models]))

    rng  = random.Random(seed)
    rhos = []
    for _ in range(n_iter):
        sample_qids = rng.choices(all_qids, k=len(all_qids))
        scores_a, scores_b = {}, {}
        for m in models:
            vals_a = [data_a[m].get(q, None) for q in sample_qids]
            vals_b = [data_b[m].get(q, None) for q in sample_qids]
            vals_a = [v for v in vals_a if v is not None]
            vals_b = [v for v in vals_b if v is not None]
            if vals_a:
                scores_a[m] = sum(vals_a) / len(vals_a)
            if vals_b:
                scores_b[m] = sum(vals_b) / len(vals_b)
        rhos.append(spearman_rho(scores_a, scores_b))

    return [r for r in rhos if not math.isnan(r)]


# ── 텍스트 요약 ───────────────────────────────────────────────────────────────
def print_summary(results: list[dict]):
    print("\n" + "=" * 65)
    print(f"  Cross-Judge Spearman ρ — Bootstrap 95% CI (n={N_BOOTSTRAP:,})")
    print("=" * 65)
    print(f"\n  {'Judge 쌍':<20} {'ρ (관측)':>10} {'95% CI':>22}")
    print("-" * 56)
    for r in results:
        ci = f"[{r['ci_lower']:.3f}, {r['ci_upper']:.3f}]"
        print(f"  {r['pair']:<20} {r['rho_observed']:>10.3f}  {ci:>22}")
    print()


# ── CSV 저장 ──────────────────────────────────────────────────────────────────
def save_csv(results: list[dict], output_path: Path):
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["pair", "rho_observed",
                                               "ci_lower", "ci_upper",
                                               "ci_width", "n_bootstrap"])
        writer.writeheader()
        writer.writerows(results)
    print(f"[saved] {output_path}")


# ── 시각화 ────────────────────────────────────────────────────────────────────
PAIR_COLORS = {"7B–14B": "#90CAF9", "7B–32B": "#42A5F5", "14B–32B": "#1565C0"}

def make_figure(results: list[dict], output_path: Path):
    fig, ax = plt.subplots(figsize=(8, 5))
    fig.suptitle(f"Cross-Judge Spearman ρ with 95% Bootstrap CI\n(n={N_BOOTSTRAP:,} iterations, question-level resampling)",
                 fontsize=11, fontweight="bold")

    pairs  = [r["pair"] for r in results]
    rhos   = [r["rho_observed"] for r in results]
    lowers = [r["ci_lower"] for r in results]
    uppers = [r["ci_upper"] for r in results]
    colors = [PAIR_COLORS.get(p, "#888888") for p in pairs]

    x = np.arange(len(pairs))
    bars = ax.bar(x, rhos, color=colors, edgecolor="white", width=0.5, alpha=0.85)
    ax.errorbar(x, rhos,
                yerr=[np.array(rhos) - np.array(lowers),
                      np.array(uppers) - np.array(rhos)],
                fmt="none", color="black", capsize=6, linewidth=1.5)

    ax.set_xticks(x)
    ax.set_xticklabels([f"Judge\n{p}" for p in pairs], fontsize=9)
    ax.set_ylabel("Spearman ρ")
    ax.set_ylim(0, 1.15)
    ax.axhline(0.75, color="gray", linestyle="--", linewidth=1, alpha=0.6, label="ρ=0.75 reference")
    ax.legend(fontsize=8)

    for bar, rho, lo, hi in zip(bars, rhos, lowers, uppers):
        cx = bar.get_x() + bar.get_width() / 2
        ax.text(cx, hi + 0.03, f"ρ={rho:.3f}\n[{lo:.3f}, {hi:.3f}]",
                ha="center", va="bottom", fontsize=8.5)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[saved] {output_path}")


# ── 메인 ──────────────────────────────────────────────────────────────────────
def main():
    print("Single-grade 데이터 로드 중...")
    judge_data = {}
    for judge, jdir in PHASE3_SINGLE.items():
        if not jdir.exists():
            print(f"[skip] {jdir} 없음")
            continue
        judge_data[judge] = load_single_grade(jdir)
        models = list(judge_data[judge].keys())
        print(f"  judge_{judge}: {len(models)}개 모델")

    pairs = [("7B", "14B"), ("7B", "32B"), ("14B", "32B")]
    results = []

    for ja, jb in pairs:
        pair_label = f"{ja}–{jb}"
        print(f"Bootstrap 계산 중: {pair_label} ...")

        # 관측 ρ
        scores_a = {m: sum(judge_data[ja][m].values()) / len(judge_data[ja][m])
                    for m in judge_data[ja]}
        scores_b = {m: sum(judge_data[jb][m].values()) / len(judge_data[jb][m])
                    for m in judge_data[jb]}
        rho_obs = spearman_rho(scores_a, scores_b)

        # Bootstrap
        rhos = bootstrap_rho(judge_data[ja], judge_data[jb], N_BOOTSTRAP, SEED)
        ci_lo = float(np.percentile(rhos, 2.5))
        ci_hi = float(np.percentile(rhos, 97.5))

        results.append({
            "pair":         pair_label,
            "rho_observed": round(rho_obs, 4),
            "ci_lower":     round(ci_lo, 4),
            "ci_upper":     round(ci_hi, 4),
            "ci_width":     round(ci_hi - ci_lo, 4),
            "n_bootstrap":  len(rhos),
        })
        print(f"  ρ={rho_obs:.3f}  95% CI=[{ci_lo:.3f}, {ci_hi:.3f}]")

    print_summary(results)
    save_csv(results, DATA_DIR / "results_bootstrap_ci.csv")
    make_figure(results, FIG_DIR / "fig14_bootstrap_ci.png")
    print("완료.")


if __name__ == "__main__":
    main()
