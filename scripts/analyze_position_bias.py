"""
Position Bias 정량화 분석

연구 질문:
  Pairwise inconsistency 발생 시 먼저 제시된 모델이 유리한가?
  Judge 크기가 커질수록 position bias가 줄어드는가?

방법론:
  inconsistent 판정 레코드에서:
    - AB 순서(A가 position 1): winner_ab == "A" → first-position 승
    - BA 순서(B가 position 1): winner_ba == "B" → first-position 승
  first-position 승리 비율이 0.5 초과 → first-position bias 존재

출력:
  data/results_position_bias.csv
  figures/fig11_position_bias.png
"""

import json
import csv
import statistics
from pathlib import Path
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

ROOT     = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
FIG_DIR  = ROOT / "figures"
FIG_DIR.mkdir(exist_ok=True)

PHASE3_PAIRWISE = {
    "7B":  DATA_DIR / "judgments_phase3" / "judge_7B"  / "pairwise",
    "14B": DATA_DIR / "judgments_phase3" / "judge_14B" / "pairwise",
    "32B": DATA_DIR / "judgments_phase3" / "judge_32B" / "pairwise",
}

CATEGORIES = ["writing", "roleplay", "extraction", "reasoning",
              "math", "coding", "stem", "humanities"]
CAT_LABEL  = {c: c.capitalize() for c in CATEGORIES}
CAT_LABEL["stem"] = "STEM"

# ── 데이터 로드 ───────────────────────────────────────────────────────────────
def load_pairwise(pairwise_dir: Path) -> list[dict]:
    records = []
    for fpath in sorted(pairwise_dir.glob("*.jsonl")):
        with open(fpath) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                records.append(json.loads(line))
    return records


# ── Position Bias 계산 ────────────────────────────────────────────────────────
def compute_position_bias(records: list[dict]) -> dict:
    """
    Returns:
      {
        "total":              총 레코드 수
        "inconsistent_n":     불일치 레코드 수
        "inconsistency_rate": 불일치율
        "first_pos_wins":     first-position 승리 건수
        "first_pos_rate":     first-position 승리 비율 (inconsistent 중)
        "bias":               first_pos_rate - 0.5  (양수=first bias, 음수=second bias)
        "by_category":        카테고리별 동일 딕셔너리
      }
    """
    total = len(records)
    incons = [r for r in records if r["winner"] == "inconsistent"]

    # first-position 승리: AB 순서에서 A(position-1) 승 OR BA 순서에서 B(position-1) 승
    first_wins = 0
    for r in incons:
        w_ab = r.get("winner_ab", "")
        w_ba = r.get("winner_ba", "")
        # AB 순서: model_a는 position-1
        if w_ab == "A":
            first_wins += 1
        # BA 순서: model_b는 position-1
        elif w_ba == "B":
            first_wins += 1

    incons_n = len(incons)
    rate = first_wins / incons_n if incons_n > 0 else 0.0

    # 카테고리별
    by_cat = {}
    for cat in CATEGORIES:
        cat_recs  = [r for r in records if r.get("category") == cat]
        cat_incons = [r for r in cat_recs if r["winner"] == "inconsistent"]
        cat_fw = 0
        for r in cat_incons:
            if r.get("winner_ab") == "A":
                cat_fw += 1
            elif r.get("winner_ba") == "B":
                cat_fw += 1
        cat_n = len(cat_incons)
        by_cat[cat] = {
            "total":             len(cat_recs),
            "inconsistent_n":    cat_n,
            "inconsistency_rate": cat_n / len(cat_recs) if cat_recs else 0.0,
            "first_pos_wins":    cat_fw,
            "first_pos_rate":    cat_fw / cat_n if cat_n > 0 else 0.0,
            "bias":              (cat_fw / cat_n - 0.5) if cat_n > 0 else 0.0,
        }

    return {
        "total":              total,
        "inconsistent_n":     incons_n,
        "inconsistency_rate": incons_n / total if total > 0 else 0.0,
        "first_pos_wins":     first_wins,
        "first_pos_rate":     rate,
        "bias":               rate - 0.5,
        "by_category":        by_cat,
    }


# ── 텍스트 출력 ───────────────────────────────────────────────────────────────
def print_summary(results: dict[str, dict]):
    print("\n" + "=" * 65)
    print("  Position Bias 분석 요약")
    print("=" * 65)

    print(f"\n{'Judge':<8} {'Incons율':>10} {'First-pos율':>12} {'Bias':>8}  판정")
    print("-" * 55)
    for judge, r in results.items():
        bias = r["bias"]
        verdict = ("→ FIRST-POS bias" if bias > 0.05
                   else "→ SECOND-POS bias" if bias < -0.05
                   else "→ 편향 없음")
        print(f"  {judge:<6}  {r['inconsistency_rate']:>9.1%}  "
              f"{r['first_pos_rate']:>11.1%}  {bias:>+7.3f}  {verdict}")

    # 카테고리별 (32B 기준)
    r32 = results.get("32B")
    if r32:
        print("\n[32B judge — 카테고리별 position bias]")
        print(f"  {'Category':<14} {'Incons N':>9} {'First-pos율':>12} {'Bias':>8}")
        print("-" * 50)
        cats_sorted = sorted(CATEGORIES,
                             key=lambda c: r32["by_category"][c]["bias"],
                             reverse=True)
        for cat in cats_sorted:
            s = r32["by_category"][cat]
            if s["inconsistent_n"] == 0:
                continue
            print(f"  {CAT_LABEL[cat]:<14} {s['inconsistent_n']:>9}  "
                  f"{s['first_pos_rate']:>11.1%}  {s['bias']:>+7.3f}")
    print()


# ── CSV 저장 ──────────────────────────────────────────────────────────────────
def save_csv(results: dict[str, dict], output_path: Path):
    rows = []
    for judge, r in results.items():
        rows.append({
            "judge": judge,
            "category": "overall",
            "total_pairs": r["total"],
            "inconsistent_n": r["inconsistent_n"],
            "inconsistency_rate": round(r["inconsistency_rate"], 4),
            "first_pos_wins": r["first_pos_wins"],
            "first_pos_rate": round(r["first_pos_rate"], 4),
            "bias": round(r["bias"], 4),
        })
        for cat in CATEGORIES:
            s = r["by_category"][cat]
            rows.append({
                "judge": judge,
                "category": cat,
                "total_pairs": s["total"],
                "inconsistent_n": s["inconsistent_n"],
                "inconsistency_rate": round(s["inconsistency_rate"], 4),
                "first_pos_wins": s["first_pos_wins"],
                "first_pos_rate": round(s["first_pos_rate"], 4),
                "bias": round(s["bias"], 4),
            })
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"[saved] {output_path}")


# ── 시각화 ────────────────────────────────────────────────────────────────────
JUDGE_COLORS = {"7B": "#90CAF9", "14B": "#42A5F5", "32B": "#1565C0"}

def make_figure(results: dict[str, dict], output_path: Path):
    fig, axes = plt.subplots(1, 3, figsize=(17, 6))
    fig.suptitle("Position Bias Analysis — Phase 3 Pairwise Judgments",
                 fontsize=14, fontweight="bold", y=1.01)

    judges = ["7B", "14B", "32B"]

    # ── Panel A: Judge별 inconsistency율 vs first-position 승률 ───────────────
    ax = axes[0]
    inc_rates  = [results[j]["inconsistency_rate"] * 100 for j in judges]
    fp_rates   = [results[j]["first_pos_rate"] * 100 for j in judges]
    x = np.arange(len(judges))
    w = 0.35

    b1 = ax.bar(x - w/2, inc_rates, w, label="Inconsistency Rate",
                color="#EF9A9A", edgecolor="white")
    b2 = ax.bar(x + w/2, fp_rates,  w, label="First-Position Win Rate",
                color=[JUDGE_COLORS[j] for j in judges], edgecolor="white")

    ax.axhline(50, color="gray", linestyle="--", linewidth=1.2, alpha=0.7, label="50% baseline")
    ax.set_xticks(x)
    ax.set_xticklabels([f"Qwen2.5\n{j}" for j in judges])
    ax.set_ylabel("Rate (%)")
    ax.set_ylim(0, 95)
    ax.set_title("(A) Inconsistency Rate vs\nFirst-Position Win Rate")
    ax.legend(fontsize=8.5, framealpha=0.85)
    for bar in list(b1) + list(b2):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f"{bar.get_height():.1f}%", ha="center", va="bottom", fontsize=8.5)

    # ── Panel B: Position Bias (first_pos_rate - 0.5) by judge ───────────────
    ax = axes[1]
    biases = [results[j]["bias"] * 100 for j in judges]
    bar_colors = ["#EF5350" if b > 5 else "#66BB6A" if b < -5 else "#BDBDBD"
                  for b in biases]
    bars = ax.bar(judges, biases, color=bar_colors, edgecolor="white", width=0.5)
    ax.axhline(0, color="black", linewidth=1)
    ax.axhline(5, color="#EF5350", linestyle="--", linewidth=1, alpha=0.6, label="+5% threshold")
    ax.axhline(-5, color="#66BB6A", linestyle="--", linewidth=1, alpha=0.6)
    ax.set_ylabel("Bias = First-pos Rate − 50% (pp)")
    ax.set_title("(B) Position Bias Magnitude\nby Judge Size")
    ax.set_ylim(-20, 35)
    for bar, bias, judge in zip(bars, biases, judges):
        label = "first-pos bias" if bias > 5 else "second-pos bias" if bias < -5 else "neutral"
        ax.text(bar.get_x() + bar.get_width()/2,
                bias + (1.5 if bias >= 0 else -3),
                f"{bias:+.1f}pp\n({label})",
                ha="center", va="bottom" if bias >= 0 else "top",
                fontsize=9, fontweight="bold")
    red_patch   = mpatches.Patch(color="#EF5350", label="First-pos bias (>+5pp)")
    green_patch = mpatches.Patch(color="#66BB6A", label="Second-pos bias (<-5pp)")
    gray_patch  = mpatches.Patch(color="#BDBDBD", label="Neutral")
    ax.legend(handles=[red_patch, green_patch, gray_patch], fontsize=8, loc="upper right")

    # ── Panel C: 카테고리별 bias (32B judge) ─────────────────────────────────
    ax = axes[2]
    r32 = results["32B"]
    cats_sorted = sorted(
        [c for c in CATEGORIES if r32["by_category"][c]["inconsistent_n"] > 0],
        key=lambda c: r32["by_category"][c]["bias"]
    )
    cat_biases = [r32["by_category"][c]["bias"] * 100 for c in cats_sorted]
    cat_ns     = [r32["by_category"][c]["inconsistent_n"] for c in cats_sorted]
    bar_colors_c = ["#EF5350" if b > 5 else "#66BB6A" if b < -5 else "#BDBDBD"
                    for b in cat_biases]

    y = np.arange(len(cats_sorted))
    bars_c = ax.barh(y, cat_biases, color=bar_colors_c, edgecolor="white", height=0.6)
    ax.axvline(0, color="black", linewidth=1)
    ax.axvline(5,  color="#EF5350", linestyle="--", linewidth=1, alpha=0.5)
    ax.axvline(-5, color="#66BB6A", linestyle="--", linewidth=1, alpha=0.5)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{CAT_LABEL[c]} (n={cat_ns[i]})"
                        for i, c in enumerate(cats_sorted)], fontsize=9)
    ax.set_xlabel("Bias (pp)")
    ax.set_title("(C) Position Bias by Category\n(Qwen2.5-32B Judge)")
    for bar, bias in zip(bars_c, cat_biases):
        ax.text(bias + (0.5 if bias >= 0 else -0.5), bar.get_y() + bar.get_height()/2,
                f"{bias:+.1f}", va="center", ha="left" if bias >= 0 else "right",
                fontsize=8.5)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[saved] {output_path}")


# ── 메인 ──────────────────────────────────────────────────────────────────────
def main():
    results = {}
    for judge, pdir in PHASE3_PAIRWISE.items():
        if not pdir.exists():
            print(f"[skip] {pdir} 없음")
            continue
        print(f"Phase 3 {judge} pairwise 로드 중...")
        records = load_pairwise(pdir)
        print(f"  → {len(records)}개 레코드")
        results[judge] = compute_position_bias(records)

    print_summary(results)

    save_csv(results, DATA_DIR / "results_position_bias.csv")
    make_figure(results, FIG_DIR / "fig11_position_bias.png")

    print("완료.")


if __name__ == "__main__":
    main()
