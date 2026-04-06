"""
앙상블 Judge 설계 개선 비교

현재 설계 vs 개선 설계:
  현재:  "inconsistent"를 하나의 표로 취급 → 2/3 다수결
  개선:  "inconsistent"를 기권으로 처리 → 결정적 표(A/B)가 모두 일치하면 winner

차이점:
  예: 7B=inconsistent, 14B=inconsistent, 32B=A
    현재 → inconsistent (inconsistent 2표)
    개선 → A (결정적 표 1개, 충돌 없음)

출력:
  data/results_ensemble_v2.csv
  figures/fig13_ensemble_v2.png
"""

import json
import csv
from pathlib import Path
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
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
def load_pairwise(pairwise_dir: Path) -> dict:
    records = {}
    for fpath in sorted(pairwise_dir.glob("*.jsonl")):
        with open(fpath) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                key = (r["question_id"], r["model_a"], r["model_b"])
                records[key] = {
                    "winner":   r["winner"],
                    "category": r.get("category", "unknown"),
                }
    return records


# ── 앙상블 방식 2종 ───────────────────────────────────────────────────────────
def majority_vote_current(votes: list[str]) -> str:
    """현재 설계: inconsistent를 표로 취급, 2/3 다수결."""
    counts = Counter(votes)
    top, cnt = counts.most_common(1)[0]
    return top if cnt >= 2 else "inconsistent"


def majority_vote_abstain(votes: list[str]) -> str:
    """
    개선 설계: inconsistent를 기권으로 처리.
    결정적 표(A/B)가 하나라도 있고 모두 같은 결론이면 winner.
    결정적 표가 없거나 충돌하면 inconsistent.
    """
    decisive = [v for v in votes if v != "inconsistent"]
    if not decisive:
        return "inconsistent"
    if len(set(decisive)) == 1:   # 모두 같은 결론 (충돌 없음)
        return decisive[0]
    return "inconsistent"          # 충돌


def compute_ensemble(judge_data: dict, vote_fn) -> dict:
    keys = set.intersection(*[set(judge_data[j].keys()) for j in ["7B", "14B", "32B"]])
    ensemble = {}
    for key in keys:
        votes = [judge_data[j][key]["winner"] for j in ["7B", "14B", "32B"]]
        cat   = judge_data["32B"][key]["category"]
        ensemble[key] = {
            "winner":   vote_fn(votes),
            "category": cat,
            "votes":    votes,
        }
    return ensemble


# ── 통계 계산 ─────────────────────────────────────────────────────────────────
def compute_stats(records: dict) -> dict:
    def _s(recs):
        total  = len(recs)
        incons = sum(1 for r in recs if r["winner"] == "inconsistent")
        decisive = total - incons
        return {
            "total": total,
            "inconsistent_n": incons,
            "decisive_n": decisive,
            "inconsistency_rate": incons / total if total else 0.0,
            "decisive_rate": decisive / total if total else 0.0,
        }

    all_recs = list(records.values())
    return {
        "overall":     _s(all_recs),
        "by_category": {cat: _s([r for r in all_recs if r["category"] == cat])
                        for cat in CATEGORIES},
    }


# ── 두 설계 간 차이 분석 ──────────────────────────────────────────────────────
def compare_designs(ens_current: dict, ens_abstain: dict) -> dict:
    """
    두 설계 결과가 다른 케이스 분류:
      current=inconsistent, abstain=winner → 기권 방식이 결정적으로 처리
      current=winner, abstain=inconsistent → 기권 방식이 더 보수적
    """
    changed_to_winner   = 0
    changed_to_incons   = 0
    total = len(ens_current)
    for key in ens_current:
        wc = ens_current[key]["winner"]
        wa = ens_abstain[key]["winner"]
        if wc == "inconsistent" and wa != "inconsistent":
            changed_to_winner += 1
        elif wc != "inconsistent" and wa == "inconsistent":
            changed_to_incons += 1
    return {
        "total": total,
        "changed_to_winner": changed_to_winner,
        "changed_to_incons": changed_to_incons,
        "same": total - changed_to_winner - changed_to_incons,
    }


# ── 텍스트 요약 ───────────────────────────────────────────────────────────────
def print_summary(single_stats, ens_cur_stats, ens_abs_stats, diff):
    print("\n" + "=" * 65)
    print("  앙상블 Judge 설계 비교")
    print("=" * 65)
    print(f"\n{'방식':<30} {'Inconsistency율':>16} {'Decisive율':>14}")
    print("-" * 66)
    for j in ["7B", "14B", "32B"]:
        overall = single_stats[j]["overall"]
        print(f"  단일 {j:<24} {overall['inconsistency_rate']:>15.2%} {overall['decisive_rate']:>13.2%}")
    overall = ens_cur_stats["overall"]
    print(f"  {'앙상블 현재 (다수결)':<28} {overall['inconsistency_rate']:>15.2%} {overall['decisive_rate']:>13.2%}")
    overall = ens_abs_stats["overall"]
    print(f"  {'앙상블 개선 (기권 방식)':<28} {overall['inconsistency_rate']:>15.2%} {overall['decisive_rate']:>13.2%}")

    print(f"\n[두 설계 차이 분석] (총 {diff['total']}쌍)")
    print(f"  동일 결과:                {diff['same']:>6}쌍 ({diff['same']/diff['total']:.1%})")
    print(f"  현재=incons → 개선=winner: {diff['changed_to_winner']:>6}쌍 ({diff['changed_to_winner']/diff['total']:.1%})")
    print(f"  현재=winner → 개선=incons: {diff['changed_to_incons']:>6}쌍 ({diff['changed_to_incons']/diff['total']:.1%})")

    print("\n[카테고리별 inconsistency율 — 개선 설계]")
    print(f"  {'Category':<14} {'32B':>8} {'현재앙상블':>12} {'개선앙상블':>12} {'감소':>8}")
    print("-" * 58)
    for cat in CATEGORIES:
        r32  = single_stats["32B"]["by_category"][cat]["inconsistency_rate"]
        rcur = ens_cur_stats["by_category"][cat]["inconsistency_rate"]
        rabs = ens_abs_stats["by_category"][cat]["inconsistency_rate"]
        diff_pp = (rabs - r32) * 100
        sign = f"{diff_pp:+.1f}pp"
        print(f"  {CAT_LABEL[cat]:<14} {r32:>7.1%}  {rcur:>11.1%}  {rabs:>11.1%}  {sign:>8}")
    print()


# ── CSV 저장 ──────────────────────────────────────────────────────────────────
def save_csv(single_stats, ens_cur_stats, ens_abs_stats, output_path: Path):
    rows = []
    for label, stats in [
        ("single_7B",          single_stats["7B"]),
        ("single_14B",         single_stats["14B"]),
        ("single_32B",         single_stats["32B"]),
        ("ensemble_current",   ens_cur_stats),
        ("ensemble_abstain",   ens_abs_stats),
    ]:
        s = stats["overall"]
        rows.append({"method": label, "category": "overall",
                     "total_pairs": s["total"], "inconsistent_n": s["inconsistent_n"],
                     "decisive_n": s["decisive_n"],
                     "inconsistency_rate": round(s["inconsistency_rate"], 4),
                     "decisive_rate": round(s["decisive_rate"], 4)})
        for cat in CATEGORIES:
            s = stats["by_category"][cat]
            rows.append({"method": label, "category": cat,
                         "total_pairs": s["total"], "inconsistent_n": s["inconsistent_n"],
                         "decisive_n": s["decisive_n"],
                         "inconsistency_rate": round(s["inconsistency_rate"], 4),
                         "decisive_rate": round(s["decisive_rate"], 4)})

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"[saved] {output_path}")


# ── 시각화 ────────────────────────────────────────────────────────────────────
COLORS = {"7B": "#90CAF9", "14B": "#42A5F5", "32B": "#1565C0",
          "cur": "#FF7043", "abs": "#E53935"}

def make_figure(single_stats, ens_cur_stats, ens_abs_stats, diff, output_path: Path):
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle("Ensemble Design Comparison: Majority Vote vs Abstain",
                 fontsize=13, fontweight="bold")

    # ── Panel A: Overall 비교 ─────────────────────────────────────────────────
    ax = axes[0]
    labels = ["Single\n7B", "Single\n14B", "Single\n32B", "Ensemble\nMajority", "Ensemble\nAbstain"]
    rates  = [
        single_stats["7B"]["overall"]["inconsistency_rate"] * 100,
        single_stats["14B"]["overall"]["inconsistency_rate"] * 100,
        single_stats["32B"]["overall"]["inconsistency_rate"] * 100,
        ens_cur_stats["overall"]["inconsistency_rate"] * 100,
        ens_abs_stats["overall"]["inconsistency_rate"] * 100,
    ]
    colors = [COLORS["7B"], COLORS["14B"], COLORS["32B"], COLORS["cur"], COLORS["abs"]]
    x = np.arange(len(labels))
    bars = ax.bar(x, rates, color=colors, edgecolor="white", width=0.55)
    ax.axhline(rates[2], color="#1565C0", linestyle="--", linewidth=1, alpha=0.5,
               label=f"Single 32B ({rates[2]:.1f}%)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8.5)
    ax.set_ylabel("Inconsistency Rate (%)")
    ax.set_ylim(0, 95)
    ax.set_title("(A) Overall Inconsistency Rate")
    ax.legend(fontsize=8)
    for bar, rate in zip(bars, rates):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{rate:.1f}%", ha="center", va="bottom", fontsize=8.5, fontweight="bold")

    # ── Panel B: 카테고리별 비교 (32B vs 개선 앙상블) ─────────────────────────
    ax = axes[1]
    cats = CATEGORIES
    r32  = [single_stats["32B"]["by_category"][c]["inconsistency_rate"] * 100 for c in cats]
    rabs = [ens_abs_stats["by_category"][c]["inconsistency_rate"] * 100 for c in cats]
    rcur = [ens_cur_stats["by_category"][c]["inconsistency_rate"] * 100 for c in cats]

    y = np.arange(len(cats))
    w = 0.25
    ax.barh(y - w, r32,  w, color=COLORS["32B"], label="Single 32B",      edgecolor="white")
    ax.barh(y,     rcur, w, color=COLORS["cur"],  label="Ensemble majority vote", edgecolor="white")
    ax.barh(y + w, rabs, w, color=COLORS["abs"],  label="Ensemble abstain", edgecolor="white")
    ax.set_yticks(y)
    ax.set_yticklabels([CAT_LABEL[c] for c in cats])
    ax.set_xlabel("Inconsistency Rate (%)")
    ax.set_title("(B) Category-level Comparison\n(Single 32B vs Ensemble)")
    ax.legend(fontsize=8, loc="lower right")

    # 두 설계 차이 주석
    ax2 = ax.twinx()
    ax2.set_ylim(ax.get_ylim())
    ax2.set_yticks([])
    axes[0].text(
        0.03, 0.08,
        f"Abstain vs. majority:\n+{diff['changed_to_winner']} resolved / -{diff['changed_to_incons']} abstained",
        transform=axes[0].transAxes,
        ha="left",
        va="bottom",
        fontsize=7.8,
        color="gray",
        bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="none", alpha=0.85),
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[saved] {output_path}")


# ── 메인 ──────────────────────────────────────────────────────────────────────
def main():
    judge_data = {}
    for judge, pdir in PHASE3_PAIRWISE.items():
        if not pdir.exists():
            print(f"[skip] {pdir} 없음")
            continue
        print(f"judge_{judge} pairwise 로드 중...")
        judge_data[judge] = load_pairwise(pdir)

    single_stats = {j: compute_stats(judge_data[j]) for j in judge_data}

    print("앙상블 계산 중...")
    ens_current = compute_ensemble(judge_data, majority_vote_current)
    ens_abstain = compute_ensemble(judge_data, majority_vote_abstain)

    ens_cur_stats = compute_stats(ens_current)
    ens_abs_stats = compute_stats(ens_abstain)

    diff = compare_designs(ens_current, ens_abstain)

    print_summary(single_stats, ens_cur_stats, ens_abs_stats, diff)

    save_csv(single_stats, ens_cur_stats, ens_abs_stats, DATA_DIR / "results_ensemble_v2.csv")
    make_figure(single_stats, ens_cur_stats, ens_abs_stats, diff, FIG_DIR / "fig13_ensemble_v2.png")

    print("완료.")


if __name__ == "__main__":
    main()
