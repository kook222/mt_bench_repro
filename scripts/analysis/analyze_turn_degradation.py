"""
Turn 1 vs Turn 2 성능 저하 분석

연구 질문:
  멀티턴에서 모델별·카테고리별 Turn 2 품질 저하 패턴은 어떻게 다른가?
  Judge 크기(Phase 3)별로 Turn 2 채점 패턴이 달라지는가?

출력:
  data/results_turn_degradation.csv   — 모델×카테고리별 δ(T2-T1) 테이블
  figures/fig10_turn_degradation.png  — 4-panel 시각화
"""

import json
import os
import csv
from pathlib import Path
from collections import defaultdict
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ── 경로 설정 ─────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
FIG_DIR = ROOT / "figures"
FIG_DIR.mkdir(exist_ok=True)

# Phase 3 데이터만 사용 (self-judge / 동일 패밀리 편향 제거)
# Phase 2 데이터(data/judgments_phase2/)는 Qwen2.5-14B judge → 분석에서 제외
PHASE3_JUDGE_DIRS = {
    "7B":  DATA_DIR / "judgments_phase3" / "judge_7B"  / "single_grade",
    "14B": DATA_DIR / "judgments_phase3" / "judge_14B" / "single_grade",
    "32B": DATA_DIR / "judgments_phase3" / "judge_32B" / "single_grade",
}
# 주 분석에 사용할 judge (불일치율 가장 낮음)
PRIMARY_JUDGE_DIR = PHASE3_JUDGE_DIRS["32B"]

CATEGORIES = ["writing", "roleplay", "extraction", "reasoning",
              "math", "coding", "stem", "humanities"]

# 카테고리 표시명
CAT_LABEL = {
    "writing": "Writing", "roleplay": "Roleplay", "extraction": "Extraction",
    "reasoning": "Reasoning", "math": "Math", "coding": "Coding",
    "stem": "STEM", "humanities": "Humanities",
}

# ── 데이터 로드 ───────────────────────────────────────────────────────────────
def load_judgments(judge_dir: Path) -> dict:
    """
    Returns:
        {model_id: [(question_id, category, score_turn1, score_turn2), ...]}
    """
    data = defaultdict(list)
    for fpath in sorted(judge_dir.glob("*.jsonl")):
        model_id = fpath.stem
        with open(fpath) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                t1 = rec.get("score_turn1")
                t2 = rec.get("score_turn2")
                cat = rec.get("category", "unknown")
                qid = rec.get("question_id")
                if t1 is None or t2 is None:
                    continue
                if t1 < 0 or t2 < 0:   # 파싱 실패(-1.0) 제외
                    continue
                data[model_id].append((qid, cat, float(t1), float(t2)))
    return dict(data)


def compute_delta_table(data: dict) -> dict:
    """
    Returns:
        {model_id: {category: {"t1": mean, "t2": mean, "delta": mean, "n": count}}}
    """
    result = {}
    for model, records in data.items():
        by_cat = defaultdict(list)
        for qid, cat, t1, t2 in records:
            by_cat[cat].append((t1, t2))
        cat_stats = {}
        for cat in CATEGORIES:
            pairs = by_cat.get(cat, [])
            if not pairs:
                continue
            t1s = [p[0] for p in pairs]
            t2s = [p[1] for p in pairs]
            cat_stats[cat] = {
                "t1": statistics.mean(t1s),
                "t2": statistics.mean(t2s),
                "delta": statistics.mean([t2 - t1 for t1, t2 in pairs]),
                "n": len(pairs),
            }
        result[model] = cat_stats
    return result


# ── CSV 저장 ──────────────────────────────────────────────────────────────────
def save_csv(delta_table: dict, output_path: Path):
    rows = []
    for model, cats in delta_table.items():
        for cat, stats in cats.items():
            rows.append({
                "model": model,
                "category": cat,
                "score_turn1": round(stats["t1"], 3),
                "score_turn2": round(stats["t2"], 3),
                "delta": round(stats["delta"], 3),
                "n_questions": stats["n"],
            })
    rows.sort(key=lambda r: (r["model"], r["category"]))
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["model", "category",
                                               "score_turn1", "score_turn2",
                                               "delta", "n_questions"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"[saved] {output_path}")


# ── 시각화 ────────────────────────────────────────────────────────────────────
COLORS = [
    "#4C72B0", "#DD8452", "#55A868", "#C44E52",
    "#8172B2", "#937860", "#DA8BC3", "#8C8C8C", "#CCB974",
]

def make_figure(delta_table: dict, phase3_tables: dict, output_path: Path):
    models = sorted(delta_table.keys())
    color_map = {m: COLORS[i % len(COLORS)] for i, m in enumerate(models)}

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle("Turn 1 vs Turn 2 Performance Analysis", fontsize=15, fontweight="bold", y=0.98)

    # ── Panel A: 모델별 Overall δ 바 차트 ──────────────────────────────────────
    ax = axes[0, 0]
    overall_delta = {}
    overall_t1 = {}
    overall_t2 = {}
    for model in models:
        all_pairs = [(s["t1"], s["t2"]) for s in delta_table[model].values()]
        if all_pairs:
            overall_t1[model] = statistics.mean(p[0] for p in all_pairs)
            overall_t2[model] = statistics.mean(p[1] for p in all_pairs)
            overall_delta[model] = statistics.mean(p[1] - p[0] for p in all_pairs)

    sorted_models = sorted(overall_delta, key=lambda m: overall_delta[m])
    x = np.arange(len(sorted_models))
    bars = ax.barh(x, [overall_delta[m] for m in sorted_models],
                   color=[color_map[m] for m in sorted_models], height=0.6)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_yticks(x)
    ax.set_yticklabels([m.replace("-Instruct", "").replace("-Chat", "") for m in sorted_models], fontsize=8)
    ax.set_xlabel("δ = Turn2 − Turn1 (points)")
    ax.set_title("(A) Overall Turn2 − Turn1 Delta per Model")
    # 값 레이블
    for bar, m in zip(bars, sorted_models):
        val = overall_delta[m]
        ax.text(val + (0.01 if val >= 0 else -0.01), bar.get_y() + bar.get_height()/2,
                f"{val:+.2f}", va="center", ha="left" if val >= 0 else "right", fontsize=7.5)
    ax.set_xlim(min(overall_delta.values()) - 0.3, max(overall_delta.values()) + 0.4)

    # ── Panel B: 카테고리별 평균 δ ─────────────────────────────────────────────
    ax = axes[0, 1]
    cat_deltas = defaultdict(list)
    for model in models:
        for cat, stats in delta_table[model].items():
            cat_deltas[cat].append(stats["delta"])

    cat_means = {cat: statistics.mean(cat_deltas[cat]) for cat in CATEGORIES if cat_deltas[cat]}
    cat_stds  = {cat: statistics.stdev(cat_deltas[cat]) if len(cat_deltas[cat]) > 1 else 0
                 for cat in CATEGORIES if cat_deltas[cat]}
    sorted_cats = sorted(cat_means, key=lambda c: cat_means[c])
    y = np.arange(len(sorted_cats))

    bar_colors = ["#d62728" if cat_means[c] < 0 else "#2ca02c" for c in sorted_cats]
    ax.barh(y, [cat_means[c] for c in sorted_cats],
            xerr=[cat_stds[c] for c in sorted_cats],
            color=bar_colors, height=0.6, capsize=3, error_kw={"elinewidth": 1})
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels([CAT_LABEL[c] for c in sorted_cats])
    ax.set_xlabel("Mean δ = Turn2 − Turn1 (points)")
    ax.set_title("(B) Category-level Mean Delta (all models)")
    red_patch = mpatches.Patch(color="#d62728", label="Degradation")
    green_patch = mpatches.Patch(color="#2ca02c", label="Improvement")
    ax.legend(handles=[red_patch, green_patch], fontsize=8)

    # ── Panel C: 카테고리×모델 히트맵 ─────────────────────────────────────────
    ax = axes[1, 0]
    short_models = [m.replace("-Instruct", "").replace("-Chat", "") for m in models]
    matrix = np.full((len(CATEGORIES), len(models)), np.nan)
    for j, model in enumerate(models):
        for i, cat in enumerate(CATEGORIES):
            if cat in delta_table[model]:
                matrix[i, j] = delta_table[model][cat]["delta"]

    vmax = max(abs(np.nanmin(matrix)), abs(np.nanmax(matrix)))
    im = ax.imshow(matrix, cmap="RdYlGn", vmin=-vmax, vmax=vmax, aspect="auto")
    ax.set_xticks(np.arange(len(models)))
    ax.set_xticklabels(short_models, rotation=35, ha="right", fontsize=7.5)
    ax.set_yticks(np.arange(len(CATEGORIES)))
    ax.set_yticklabels([CAT_LABEL[c] for c in CATEGORIES])
    ax.set_title("(C) Turn2 − Turn1 Heatmap (Model × Category)")
    plt.colorbar(im, ax=ax, label="δ (points)", shrink=0.8)
    # 셀 값
    for i in range(len(CATEGORIES)):
        for j in range(len(models)):
            v = matrix[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:+.1f}", ha="center", va="center",
                        fontsize=6.5, color="black")

    # ── Panel D: Judge 크기별 Overall Turn2 저하 비교 (Phase 3 only) ──────────
    ax = axes[1, 1]
    judge_labels = ["7B", "14B", "32B"]
    judge_sources = [phase3_tables.get(k) for k in ["7B", "14B", "32B"]]

    # 모든 judge에 공통으로 존재하는 모델만 사용
    common_models = None
    for src in judge_sources:
        if src is None:
            continue
        if common_models is None:
            common_models = set(src.keys())
        else:
            common_models &= set(src.keys())
    common_models = sorted(common_models or [])

    width = 0.18
    x = np.arange(len(common_models))
    judge_colors = ["#4C72B0", "#DD8452", "#55A868", "#C44E52"]

    for k, (jlabel, src, jcolor) in enumerate(zip(judge_labels, judge_sources, judge_colors)):
        if src is None:
            continue
        deltas = []
        for model in common_models:
            all_pairs = [(s["t1"], s["t2"]) for s in src[model].values()]
            if all_pairs:
                deltas.append(statistics.mean(p[1] - p[0] for p in all_pairs))
            else:
                deltas.append(0.0)
        offset = (k - 1.0) * width
        ax.bar(x + offset, deltas, width=width, label=jlabel, color=jcolor, alpha=0.85)

    ax.axhline(0, color="black", linewidth=0.8)
    short_common = [m.replace("-Instruct", "").replace("-Chat", "") for m in common_models]
    ax.set_xticks(x)
    ax.set_xticklabels(short_common, rotation=35, ha="right", fontsize=7.5)
    ax.set_ylabel("δ = Turn2 − Turn1 (points)")
    ax.set_title("(D) Judge Size Effect on Turn2 Delta")
    ax.legend(title="Judge", fontsize=8)

    plt.tight_layout(rect=[0, 0, 1, 0.97])
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[saved] {output_path}")


# ── 텍스트 요약 출력 ──────────────────────────────────────────────────────────
def print_summary(delta_table: dict):
    models = sorted(delta_table.keys())
    print("\n" + "="*60)
    print("  Turn 1 vs Turn 2 분석 요약")
    print("="*60)

    # 모델별 Overall
    print("\n[모델별 Overall δ]")
    overall = {}
    for model in models:
        pairs = [(s["t1"], s["t2"]) for s in delta_table[model].values()]
        if pairs:
            overall[model] = statistics.mean(p[1] - p[0] for p in pairs)
    for m, d in sorted(overall.items(), key=lambda x: x[1]):
        bar = "▓" * int(abs(d) * 10) if abs(d) > 0.05 else "·"
        sign = "+" if d >= 0 else ""
        print(f"  {m:<35} {sign}{d:.3f}  {bar}")

    # 카테고리별 평균
    print("\n[카테고리별 평균 δ (전체 모델)]")
    cat_deltas = defaultdict(list)
    for model in models:
        for cat, stats in delta_table[model].items():
            cat_deltas[cat].append(stats["delta"])
    for cat in sorted(cat_deltas, key=lambda c: statistics.mean(cat_deltas[c])):
        d = statistics.mean(cat_deltas[cat])
        sign = "+" if d >= 0 else ""
        print(f"  {CAT_LABEL[cat]:<15} {sign}{d:.3f}")

    print()


# ── 메인 ──────────────────────────────────────────────────────────────────────
def main():
    # 주 분석: Phase 3 judge_32B (불일치율 가장 낮음, self-judge 편향 없음)
    print("Phase 3 (judge_32B) 데이터 로드 중...")
    primary_data = load_judgments(PRIMARY_JUDGE_DIR)
    print(f"  → 모델 {len(primary_data)}개 로드 완료: {sorted(primary_data.keys())}")

    delta_table = compute_delta_table(primary_data)

    # judge 크기별 비교용 (Panel D)
    phase3_tables = {}
    for judge_size, judge_dir in PHASE3_JUDGE_DIRS.items():
        if judge_dir.exists():
            print(f"Phase 3 {judge_size} 데이터 로드 중...")
            data = load_judgments(judge_dir)
            phase3_tables[judge_size] = compute_delta_table(data)
            print(f"  → 모델 {len(data)}개 로드 완료")
        else:
            print(f"  [skip] {judge_dir} 없음")

    print_summary(delta_table)

    csv_path = DATA_DIR / "results_turn_degradation.csv"
    save_csv(delta_table, csv_path)

    fig_path = FIG_DIR / "fig10_turn_degradation.png"
    make_figure(delta_table, phase3_tables, fig_path)

    print("\n완료.")


if __name__ == "__main__":
    main()
