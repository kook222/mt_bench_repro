"""
앙상블 Judge 분석

연구 질문:
  7B + 14B + 32B 다수결 투표 시 inconsistency율이 단일 32B보다 낮아지는가?

설계:
  majority_vote(judge_7B, judge_14B, judge_32B):
    2/3 이상 일치 → winner 선언
    모두 다름     → inconsistent

출력:
  data/results_ensemble_judge.csv
  figures/fig12_ensemble_judge.png
"""

import json
import csv
from pathlib import Path
from collections import defaultdict, Counter

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
def load_pairwise(pairwise_dir: Path) -> dict:
    """
    Returns:
        {(question_id, model_a, model_b): {"winner": ..., "category": ...}}
    """
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


# ── 다수결 앙상블 ─────────────────────────────────────────────────────────────
def majority_vote(votes: list[str]) -> str:
    """
    votes: 각 judge의 winner (모델명 or "inconsistent")
    2/3 이상 일치 → winner, 모두 다름 → "inconsistent"
    """
    counts = Counter(votes)
    most_common, count = counts.most_common(1)[0]
    if count >= 2:
        return most_common
    return "inconsistent"


def compute_ensemble(judge_data: dict[str, dict], judges: list[str]) -> dict:
    """
    judge_data: {"7B": {key: record}, "14B": ..., "32B": ...}
    judges: 사용할 judge 목록 (e.g. ["7B","14B","32B"] or ["14B","32B"])
    Returns ensemble records {key: {"winner": ..., "category": ...}}
    """
    keys = set.intersection(*[set(judge_data[j].keys()) for j in judges])
    ref  = judges[-1]  # category 참조용
    ensemble = {}
    for key in keys:
        votes = [judge_data[j][key]["winner"] for j in judges]
        cat   = judge_data[ref][key]["category"]
        ensemble[key] = {
            "winner":   majority_vote(votes),
            "category": cat,
            "votes":    votes,
        }
    return ensemble


# ── 통계 계산 ─────────────────────────────────────────────────────────────────
def compute_stats(records: dict) -> dict:
    """
    Returns {"overall": {...}, "by_category": {cat: {...}}}
    """
    def _stats(recs):
        total = len(recs)
        incons = sum(1 for r in recs if r["winner"] == "inconsistent")
        return {
            "total":              total,
            "inconsistent_n":     incons,
            "inconsistency_rate": incons / total if total else 0.0,
        }

    all_recs = list(records.values())
    by_cat = {}
    for cat in CATEGORIES:
        cat_recs = [r for r in all_recs if r["category"] == cat]
        by_cat[cat] = _stats(cat_recs)

    return {"overall": _stats(all_recs), "by_category": by_cat}


# ── 텍스트 요약 ───────────────────────────────────────────────────────────────
def print_summary(single_stats: dict[str, dict], ensemble_all: dict, ensemble_14_32: dict):
    print("\n" + "=" * 65)
    print("  앙상블 Judge 분석 요약")
    print("=" * 65)

    print(f"\n{'방식':<26} {'Inconsistency율':>16} {'총 쌍':>8}")
    print("-" * 54)
    for judge in ["7B", "14B", "32B"]:
        s = single_stats[judge]["overall"]
        print(f"  단일 {judge:<20} {s['inconsistency_rate']:>15.2%}  {s['total']:>7}")
    s = ensemble_14_32["overall"]
    print(f"  {'앙상블 (14B+32B)':<24} {s['inconsistency_rate']:>15.2%}  {s['total']:>7}")
    s = ensemble_all["overall"]
    print(f"  {'앙상블 (7B+14B+32B)':<24} {s['inconsistency_rate']:>15.2%}  {s['total']:>7}")

    print("\n[카테고리별 inconsistency율]")
    print(f"  {'Category':<14} {'7B':>7} {'14B':>7} {'32B':>7} {'14+32':>7} {'7+14+32':>9}")
    print("-" * 58)
    for cat in CATEGORIES:
        r7   = single_stats["7B"]["by_category"][cat]["inconsistency_rate"]
        r14  = single_stats["14B"]["by_category"][cat]["inconsistency_rate"]
        r32  = single_stats["32B"]["by_category"][cat]["inconsistency_rate"]
        e14  = ensemble_14_32["by_category"][cat]["inconsistency_rate"]
        eall = ensemble_all["by_category"][cat]["inconsistency_rate"]
        print(f"  {CAT_LABEL[cat]:<14} {r7:>6.1%}  {r14:>6.1%}  {r32:>6.1%}  {e14:>6.1%}  {eall:>8.1%}")
    print()


# ── CSV 저장 ──────────────────────────────────────────────────────────────────
def save_csv(single_stats: dict[str, dict], ensemble_all: dict, ensemble_14_32: dict, output_path: Path):
    rows = []
    all_methods = [
        ("single_7B",         single_stats["7B"]),
        ("single_14B",        single_stats["14B"]),
        ("single_32B",        single_stats["32B"]),
        ("ensemble_14B_32B",  ensemble_14_32),
        ("ensemble_7B_14B_32B", ensemble_all),
    ]
    for label, stats in all_methods:
        s = stats["overall"]
        rows.append({"method": label, "category": "overall",
                     "total_pairs": s["total"],
                     "inconsistent_n": s["inconsistent_n"],
                     "inconsistency_rate": round(s["inconsistency_rate"], 4)})
        for cat in CATEGORIES:
            s = stats["by_category"][cat]
            rows.append({"method": label, "category": cat,
                         "total_pairs": s["total"],
                         "inconsistent_n": s["inconsistent_n"],
                         "inconsistency_rate": round(s["inconsistency_rate"], 4)})

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"[saved] {output_path}")


# ── 시각화 ────────────────────────────────────────────────────────────────────
COLORS = {
    "7B":      "#90CAF9",
    "14B":     "#42A5F5",
    "32B":     "#1565C0",
    "ensemble":"#E53935",
}

COLORS["ensemble_14_32"] = "#FF7043"

def make_figure(single_stats: dict[str, dict], ensemble_all: dict, ensemble_14_32: dict, output_path: Path):
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    fig.suptitle("Ensemble Judge vs Single Judge — Inconsistency Rate",
                 fontsize=13, fontweight="bold")

    methods = ["7B", "14B", "32B", "ensemble_14_32", "ensemble"]
    labels  = ["Single\n7B", "Single\n14B", "Single\n32B", "Ensemble\n14B+32B", "Ensemble\n7B+14B+32B"]
    rates   = [
        single_stats["7B"]["overall"]["inconsistency_rate"] * 100,
        single_stats["14B"]["overall"]["inconsistency_rate"] * 100,
        single_stats["32B"]["overall"]["inconsistency_rate"] * 100,
        ensemble_14_32["overall"]["inconsistency_rate"] * 100,
        ensemble_all["overall"]["inconsistency_rate"] * 100,
    ]
    colors = [COLORS[m] for m in methods]

    # ── Panel A: Overall 비교 막대 ────────────────────────────────────────────
    ax = axes[0]
    x = np.arange(len(methods))
    bars = ax.bar(x, rates, color=colors, edgecolor="white", width=0.55)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8.5)
    ax.set_ylabel("Inconsistency Rate (%)")
    ax.set_ylim(0, 95)
    ax.set_title("(A) Overall Inconsistency Rate")
    for bar, rate in zip(bars, rates):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{rate:.1f}%", ha="center", va="bottom", fontsize=8.5, fontweight="bold")

    # 32B 기준선
    ax.axhline(rates[2], color="#1565C0", linestyle="--", linewidth=1, alpha=0.5, label=f"Single 32B ({rates[2]:.1f}%)")
    ax.legend(fontsize=8)

    # ── Panel B: 카테고리별 비교 ──────────────────────────────────────────────
    ax = axes[1]
    cat_rates = {m: [] for m in methods}
    for cat in CATEGORIES:
        for j in ["7B", "14B", "32B"]:
            cat_rates[j].append(single_stats[j]["by_category"][cat]["inconsistency_rate"] * 100)
        cat_rates["ensemble_14_32"].append(ensemble_14_32["by_category"][cat]["inconsistency_rate"] * 100)
        cat_rates["ensemble"].append(ensemble_all["by_category"][cat]["inconsistency_rate"] * 100)

    y = np.arange(len(CATEGORIES))
    w = 0.15
    offsets = [-2, -1, 0, 1, 2]
    for i, (m, lbl) in enumerate(zip(methods, labels)):
        ax.barh(y + offsets[i] * w, cat_rates[m], w,
                color=COLORS[m], label=lbl.replace("\n", " "), edgecolor="white")

    ax.set_yticks(y)
    ax.set_yticklabels([CAT_LABEL[c] for c in CATEGORIES])
    ax.set_xlabel("Inconsistency Rate (%)")
    ax.set_title("(B) Inconsistency Rate by Category")
    ax.legend(fontsize=7.5, loc="lower right")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[saved] {output_path}")


# ── 메인 ──────────────────────────────────────────────────────────────────────
def main():
    # 데이터 로드
    judge_data = {}
    for judge, pdir in PHASE3_PAIRWISE.items():
        if not pdir.exists():
            print(f"[skip] {pdir} 없음")
            continue
        print(f"judge_{judge} pairwise 로드 중...")
        judge_data[judge] = load_pairwise(pdir)
        print(f"  → {len(judge_data[judge])}개 레코드")

    # 단일 judge 통계
    single_stats = {j: compute_stats(judge_data[j]) for j in judge_data}

    # 앙상블
    print("앙상블 다수결 계산 중...")
    ens_all   = compute_stats(compute_ensemble(judge_data, ["7B", "14B", "32B"]))
    ens_14_32 = compute_stats(compute_ensemble(judge_data, ["14B", "32B"]))

    print_summary(single_stats, ens_all, ens_14_32)

    save_csv(single_stats, ens_all, ens_14_32, DATA_DIR / "results_ensemble_judge.csv")
    make_figure(single_stats, ens_all, ens_14_32, FIG_DIR / "fig12_ensemble_judge.png")

    print("완료.")


if __name__ == "__main__":
    main()
