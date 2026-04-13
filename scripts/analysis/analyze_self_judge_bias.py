#!/usr/bin/env python3
"""
scripts/analysis/analyze_self_judge_bias.py

Self-Judge Bias 분석 — 핵심 분석 스크립트
==========================================

핵심 주장:
  Judge 모델이 자신과 같은 family의 eval 모델을 유리하게 채점한다.
  이 편향은 judge 선택에 따른 랭킹 불일치(Kendall τ distance)로 정량화된다.

분석 구조:
  1. Judge별 모델 랭킹 비교
     - LLaMA judge (8B / 70B)
     - Qwen judge  (7B / 14B / 32B, Phase 3 기존 데이터)
     - GPT-4o-mini judge (Phase 5 기존 데이터)

  2. Kendall τ distance (= (1 − τ) / 2)
     모든 judge 쌍의 Kendall τ distance 계산 → 히트맵으로 시각화
     τ distance가 낮을수록 두 judge의 랭킹이 유사하다.
     동일 family judge끼리 τ distance가 낮으면 family-level clustering 존재.

  3. Self-judge bias 정량화
     같은 family eval 모델의 순위를:
       - own-family judge 사용 시 순위
       - cross-family judge(GPT-4o-mini) 사용 시 순위
     의 차이를 bias score로 정의.
     bias score > 0  → 자기 judge에서 유리
     Bootstrap 95% CI로 통계적 유의성 검증.

  4. Bootstrap CI (n=10,000)
     문항 단위 리샘플링 → Kendall τ 분포 추정 → 95% CI

출력:
  data/results_self_judge_bias.csv       — judge별 랭킹 + bias score 테이블
  data/results_kendall_tau_matrix.csv    — judge 쌍별 τ distance 행렬
  figures/fig_self_judge_bias.png        — 4-panel 메인 figure

Usage:
    export PYTHONPATH=src
    python3 scripts/analysis/analyze_self_judge_bias.py
"""

from __future__ import annotations

import csv
import json
import math
import random
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── 경로 ─────────────────────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_DIR = _SCRIPT_DIR.parents[1]
if str(_PROJECT_DIR / "src") not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR / "src"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

FIGURES_DIR = _PROJECT_DIR / "figures"
FIGURES_DIR.mkdir(exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "grid.linestyle": "--",
    "figure.dpi": 150,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
    "savefig.facecolor": "white",
})

DATA_DIR = _PROJECT_DIR / "data"

# ── Judge 설정 ────────────────────────────────────────────────────────────────
# key        : 분석 내부 식별자
# label      : 그래프 표시 이름
# family     : judge family (self-judge bias 판별에 사용)
# single_dir : single_grade/ 결과 디렉토리

JUDGE_CONFIGS = [
    # LLaMA family (신규)
    {
        "key": "llama_8b",
        "label": "LLaMA-3.1-8B",
        "family": "LLaMA",
        "single_dir": DATA_DIR / "judgments_llama_judge" / "judge_8B" / "single_grade",
    },
    {
        "key": "llama_70b",
        "label": "LLaMA-3.3-70B",
        "family": "LLaMA",
        "single_dir": DATA_DIR / "judgments_llama_judge" / "judge_70B" / "single_grade",
    },
    # Qwen family (Phase 3 기존 데이터)
    {
        "key": "qwen_7b",
        "label": "Qwen2.5-7B",
        "family": "Qwen",
        "single_dir": DATA_DIR / "judgments_phase3" / "judge_7B" / "single_grade",
    },
    {
        "key": "qwen_14b",
        "label": "Qwen2.5-14B",
        "family": "Qwen",
        "single_dir": DATA_DIR / "judgments_phase3" / "judge_14B" / "single_grade",
    },
    {
        "key": "qwen_32b",
        "label": "Qwen2.5-32B",
        "family": "Qwen",
        "single_dir": DATA_DIR / "judgments_phase3" / "judge_32B" / "single_grade",
    },
    # GPT-4o-mini: 중립 reference judge
    {
        "key": "gpt4omini",
        "label": "GPT-4o-mini",
        "family": "GPT",
        "single_dir": DATA_DIR / "judgments_phase5" / "judge_gpt4omini" / "single_grade",
    },
]

# eval 모델 family 분류 (self-judge bias 측정용)
# Self-judge bias 증명 구조:
#   - LLaMA judge → LLaMA eval 모델 순위 상승 (vs GPT-mini 기준)
#   - Qwen  judge → Qwen  eval 모델 순위 상승 (vs GPT-mini 기준)
#   → 두 방향 모두 관찰 시 "bias는 구조적 문제"
EVAL_MODEL_FAMILY = {
    # LLaMA family (self-judge 핵심 검증 대상)
    "Llama-2-7b-chat":          "LLaMA",
    "Llama-3.1-8B-Instruct":    "LLaMA",
    # Qwen family (self-judge 핵심 검증 대상)
    "Qwen2.5-7B-Instruct":      "Qwen",
    "Qwen2.5-14B-Instruct":     "Qwen",
    # 중립 모델 (bias 없는 baseline)
    "SOLAR-10.7B-Instruct":     "other",
    "gemma-2-9b-it":            "other",
    "Yi-1.5-9B-Chat":           "other",
    "Zephyr-7B-beta":           "other",
    "Mistral-7B-Instruct-v0.3": "other",
    "Phi-3.5-mini-Instruct":    "other",
}

N_BOOTSTRAP = 10_000
SEED = 42
random.seed(SEED)
np.random.seed(SEED)


# ============================================================================
# 유틸
# ============================================================================

def load_single_grade(single_dir: Path) -> Dict[str, Dict[int, float]]:
    """
    single_grade/ 에서 데이터 로드.
    반환: {model_id: {question_id: avg_score}}
    파싱 실패(-1) 제외.
    """
    data: Dict[str, Dict[int, float]] = defaultdict(dict)
    if not single_dir.exists():
        return {}
    for fpath in sorted(single_dir.glob("*.jsonl")):
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
                data[model_id][r["question_id"]] = (t1 + t2) / 2.0
    return dict(data)


def model_avg_scores(grade_data: Dict[str, Dict[int, float]]) -> Dict[str, float]:
    """question_id → 모델별 평균 점수 집계."""
    return {
        model_id: sum(scores.values()) / len(scores)
        for model_id, scores in grade_data.items()
        if scores
    }


def rank_models(scores: Dict[str, float]) -> Dict[str, int]:
    """점수 내림차순 → 1-based 랭킹."""
    sorted_models = sorted(scores, key=lambda m: scores[m], reverse=True)
    return {m: i + 1 for i, m in enumerate(sorted_models)}


def kendall_tau(ranks_a: Dict[str, int], ranks_b: Dict[str, int]) -> Optional[float]:
    """
    두 랭킹의 Kendall τ (−1 ~ 1).
    공통 모델만 사용. 3개 미만이면 None.
    """
    models = sorted(set(ranks_a) & set(ranks_b))
    if len(models) < 3:
        return None
    n = len(models)
    concordant = discordant = 0
    for i in range(n):
        for j in range(i + 1, n):
            a_diff = ranks_a[models[i]] - ranks_a[models[j]]
            b_diff = ranks_b[models[i]] - ranks_b[models[j]]
            sign = a_diff * b_diff
            if sign > 0:
                concordant += 1
            elif sign < 0:
                discordant += 1
            # 동점은 무시
    total = n * (n - 1) // 2
    return (concordant - discordant) / total if total > 0 else None


def kendall_tau_distance(tau: float) -> float:
    """Kendall τ distance = (1 − τ) / 2. 범위 [0, 1]."""
    return (1.0 - tau) / 2.0


def bootstrap_kendall_ci(
    grade_a: Dict[str, Dict[int, float]],
    grade_b: Dict[str, Dict[int, float]],
    n_boot: int = N_BOOTSTRAP,
) -> Tuple[float, float, float]:
    """
    문항 단위 bootstrap으로 Kendall τ의 95% CI 계산.
    반환: (point_estimate, ci_lower, ci_upper)
    """
    # 공통 모델 + 공통 질문
    common_models = sorted(set(grade_a) & set(grade_b))
    if len(common_models) < 3:
        return float("nan"), float("nan"), float("nan")

    all_qids = sorted(
        set(qid for m in common_models for qid in grade_a[m])
        & set(qid for m in common_models for qid in grade_b[m])
    )
    if len(all_qids) < 5:
        return float("nan"), float("nan"), float("nan")

    # 점 추정
    scores_a = {m: sum(grade_a[m].get(q, 0) for q in all_qids) / len(all_qids) for m in common_models}
    scores_b = {m: sum(grade_b[m].get(q, 0) for q in all_qids) / len(all_qids) for m in common_models}
    point = kendall_tau(rank_models(scores_a), rank_models(scores_b))
    if point is None:
        return float("nan"), float("nan"), float("nan")

    # bootstrap
    boot_taus: List[float] = []
    for _ in range(n_boot):
        sampled = random.choices(all_qids, k=len(all_qids))
        sa = {m: sum(grade_a[m].get(q, 0) for q in sampled) / len(sampled) for m in common_models}
        sb = {m: sum(grade_b[m].get(q, 0) for q in sampled) / len(sampled) for m in common_models}
        t = kendall_tau(rank_models(sa), rank_models(sb))
        if t is not None:
            boot_taus.append(t)

    if not boot_taus:
        return point, float("nan"), float("nan")

    arr = np.array(boot_taus)
    return point, float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))


# ============================================================================
# Self-Judge Bias 정량화
# ============================================================================

def compute_self_judge_bias(
    judge_ranks: Dict[str, Dict[str, int]],   # {judge_key: {model: rank}}
    ref_judge_key: str = "gpt4omini",         # 중립 reference judge
) -> Dict[str, Dict[str, float]]:
    """
    family별 self-judge bias score 계산.

    bias_score(model, judge) = rank(model, ref_judge) − rank(model, own_judge)
    양수 → own_judge에서 순위 상승 (유리한 채점)
    음수 → own_judge에서 순위 하락

    반환: {judge_key: {model_id: bias_score}}
    """
    ref_ranks = judge_ranks.get(ref_judge_key)
    if not ref_ranks:
        return {}

    bias: Dict[str, Dict[str, float]] = {}
    for judge_key, ranks in judge_ranks.items():
        if judge_key == ref_judge_key:
            continue
        common_models = set(ref_ranks) & set(ranks)
        bias[judge_key] = {
            m: ref_ranks[m] - ranks[m]   # 양수 = own-judge에서 랭킹 상승
            for m in common_models
        }
    return bias


# ============================================================================
# 시각화
# ============================================================================

FAMILY_COLORS = {
    "LLaMA": "#4C72B0",
    "Qwen":  "#DD8452",
    "GPT":   "#55A868",
    "other": "#8172B2",
}


def plot_self_judge_bias(
    judge_configs: List[dict],
    judge_grades: Dict[str, Dict],
    judge_ranks: Dict[str, Dict[str, int]],
    tau_matrix: Dict[Tuple[str, str], float],
    bias_scores: Dict[str, Dict[str, float]],
    tau_ci: Dict[Tuple[str, str], Tuple[float, float, float]],
    output_path: Path,
) -> None:
    """4-panel 메인 figure 생성."""

    available_keys = [c["key"] for c in judge_configs if c["key"] in judge_ranks]
    available_labels = [c["label"] for c in judge_configs if c["key"] in judge_ranks]
    n_judges = len(available_keys)

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Self-Judge Bias Analysis: LLaMA vs Qwen vs GPT-4o-mini",
                 fontsize=14, fontweight="bold", y=1.01)

    # ── Panel A: 모델 랭킹 비교 (judge별 bar) ────────────────────────────────
    ax = axes[0, 0]
    all_models = sorted(
        set(m for ranks in judge_ranks.values() for m in ranks),
        key=lambda m: judge_ranks.get("gpt4omini", judge_ranks[available_keys[0]]).get(m, 99)
    )
    x = np.arange(len(all_models))
    width = 0.8 / max(n_judges, 1)
    for i, jkey in enumerate(available_keys):
        cfg = next(c for c in judge_configs if c["key"] == jkey)
        color = FAMILY_COLORS.get(cfg["family"], "#999999")
        ranks_here = judge_ranks[jkey]
        vals = [ranks_here.get(m, len(all_models) + 1) for m in all_models]
        offset = (i - n_judges / 2 + 0.5) * width
        ax.bar(x + offset, vals, width * 0.9, label=cfg["label"],
               color=color, alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([m.replace("-Instruct", "").replace("-v0.3", "") for m in all_models],
                       rotation=35, ha="right", fontsize=7)
    ax.set_ylabel("랭킹 (낮을수록 좋음)")
    ax.set_title("A. Judge별 모델 랭킹")
    ax.invert_yaxis()
    ax.legend(fontsize=7, ncol=2)

    # ── Panel B: Kendall τ distance 히트맵 ───────────────────────────────────
    ax = axes[0, 1]
    n = len(available_keys)
    mat = np.full((n, n), np.nan)
    for i, ki in enumerate(available_keys):
        for j, kj in enumerate(available_keys):
            if i == j:
                mat[i, j] = 0.0
            else:
                tau = tau_matrix.get((ki, kj)) or tau_matrix.get((kj, ki))
                if tau is not None:
                    mat[i, j] = kendall_tau_distance(tau)

    im = ax.imshow(mat, cmap="YlOrRd", vmin=0, vmax=0.5, aspect="auto")
    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(available_labels, rotation=40, ha="right", fontsize=8)
    ax.set_yticklabels(available_labels, fontsize=8)
    for i in range(n):
        for j in range(n):
            if not np.isnan(mat[i, j]):
                ax.text(j, i, f"{mat[i, j]:.2f}", ha="center", va="center",
                        fontsize=8, color="black" if mat[i, j] < 0.3 else "white")
    plt.colorbar(im, ax=ax, label="τ distance")
    ax.set_title("B. Kendall τ Distance 히트맵\n(낮을수록 랭킹 일치)")

    # ── Panel C: Self-Judge Bias Score (LLaMA vs Qwen) ───────────────────────
    ax = axes[1, 0]
    # LLaMA judge에서 LLaMA eval 모델의 순위 변화 vs GPT-4o-mini 기준
    llama_judge_key = "llama_70b" if "llama_70b" in bias_scores else "llama_8b"
    qwen_judge_key  = "qwen_32b" if "qwen_32b" in bias_scores else "qwen_14b"

    plot_keys = [k for k in [llama_judge_key, qwen_judge_key] if k in bias_scores]
    if plot_keys and all_models:
        x2 = np.arange(len(all_models))
        width2 = 0.35
        for i, jkey in enumerate(plot_keys):
            cfg = next((c for c in judge_configs if c["key"] == jkey), None)
            if not cfg:
                continue
            color = FAMILY_COLORS.get(cfg["family"], "#999999")
            vals = [bias_scores[jkey].get(m, 0.0) for m in all_models]
            # eval 모델이 same-family인 경우 테두리 강조
            edge_colors = [
                "red" if EVAL_MODEL_FAMILY.get(m) == cfg["family"] else "none"
                for m in all_models
            ]
            bars = ax.bar(
                x2 + (i - 0.5) * width2, vals, width2 * 0.9,
                label=cfg["label"], color=color, alpha=0.8,
                edgecolor=edge_colors, linewidth=1.5,
            )
        ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
        ax.set_xticks(x2)
        ax.set_xticklabels([m.replace("-Instruct", "").replace("-v0.3", "") for m in all_models],
                           rotation=35, ha="right", fontsize=7)
        ax.set_ylabel("Bias Score\n(ref_rank − own_rank, 양수=자기 judge에서 유리)")
        ax.set_title("C. Self-Judge Bias Score\n(GPT-4o-mini 대비, 빨간 테두리=동일 family)")
        ax.legend(fontsize=8)
    else:
        ax.text(0.5, 0.5, "LLaMA judge 데이터 없음\nrun_judge_llama_a100.sh 먼저 실행",
                ha="center", va="center", transform=ax.transAxes, fontsize=10,
                color="gray", style="italic")
        ax.set_title("C. Self-Judge Bias Score")

    # ── Panel D: Bootstrap 95% CI (Kendall τ) ────────────────────────────────
    ax = axes[1, 1]
    ci_pairs = []
    for (ki, kj), (pt, lo, hi) in tau_ci.items():
        if not (math.isnan(pt) or math.isnan(lo) or math.isnan(hi)):
            cfg_i = next((c for c in judge_configs if c["key"] == ki), None)
            cfg_j = next((c for c in judge_configs if c["key"] == kj), None)
            if cfg_i and cfg_j:
                same = cfg_i["family"] == cfg_j["family"]
                ci_pairs.append((f"{cfg_i['label']} vs\n{cfg_j['label']}", pt, lo, hi, same))

    if ci_pairs:
        ci_pairs.sort(key=lambda x: x[1], reverse=True)
        labels_ci = [p[0] for p in ci_pairs]
        pts = [p[1] for p in ci_pairs]
        los = [p[1] - p[2] for p in ci_pairs]
        his = [p[3] - p[1] for p in ci_pairs]
        colors_ci = [FAMILY_COLORS["LLaMA"] if p[4] else FAMILY_COLORS["other"] for p in ci_pairs]
        y_ci = np.arange(len(ci_pairs))
        ax.barh(y_ci, pts, xerr=[los, his], color=colors_ci, alpha=0.8,
                error_kw={"capsize": 4, "linewidth": 1.5})
        ax.set_yticks(y_ci)
        ax.set_yticklabels(labels_ci, fontsize=7)
        ax.set_xlabel("Kendall τ (높을수록 랭킹 일치)")
        ax.axvline(0, color="black", linewidth=0.8, linestyle="--")
        ax.set_title("D. Cross-Judge Kendall τ + 95% Bootstrap CI\n(동일 family 쌍 = 파란색)")
    else:
        ax.text(0.5, 0.5, "Bootstrap CI 계산 불가\n(데이터 부족)",
                ha="center", va="center", transform=ax.transAxes,
                fontsize=10, color="gray", style="italic")
        ax.set_title("D. Bootstrap 95% CI")

    plt.tight_layout()
    fig.savefig(output_path)
    plt.close()
    print(f"[OK] figure 저장: {output_path}")


# ============================================================================
# 메인
# ============================================================================

def main() -> None:
    print("=" * 60)
    print(" Self-Judge Bias Analysis")
    print("=" * 60)

    # 1. 데이터 로드
    judge_grades: Dict[str, Dict] = {}
    for cfg in JUDGE_CONFIGS:
        grade = load_single_grade(cfg["single_dir"])
        if not grade:
            print(f"[WARN] {cfg['label']} 데이터 없음: {cfg['single_dir']}")
            continue
        judge_grades[cfg["key"]] = grade
        n_models = len(grade)
        n_questions = max((len(v) for v in grade.values()), default=0)
        print(f"[OK] {cfg['label']}: {n_models}개 모델, 최대 {n_questions}개 문항")

    if len(judge_grades) < 2:
        print("[ERROR] 분석 가능한 judge가 2개 미만. 데이터 생성 후 재실행.")
        return

    # 2. 모델 랭킹 계산
    judge_ranks: Dict[str, Dict[str, int]] = {}
    for jkey, grade in judge_grades.items():
        scores = model_avg_scores(grade)
        judge_ranks[jkey] = rank_models(scores)

    # 3. Kendall τ matrix + Bootstrap CI
    tau_matrix: Dict[Tuple[str, str], float] = {}
    tau_ci: Dict[Tuple[str, str], Tuple[float, float, float]] = {}
    available_keys = list(judge_grades.keys())

    print("\n[Kendall τ + Bootstrap CI 계산 중...]")
    for ki, kj in combinations(available_keys, 2):
        tau = kendall_tau(judge_ranks[ki], judge_ranks[kj])
        tau_matrix[(ki, kj)] = tau if tau is not None else float("nan")
        pt, lo, hi = bootstrap_kendall_ci(judge_grades[ki], judge_grades[kj])
        tau_ci[(ki, kj)] = (pt, lo, hi)
        cfg_i = next(c for c in JUDGE_CONFIGS if c["key"] == ki)
        cfg_j = next(c for c in JUDGE_CONFIGS if c["key"] == kj)
        tau_str = f"{tau:.3f}" if tau is not None else "N/A"
        ci_str  = f"[{lo:.3f}, {hi:.3f}]" if not math.isnan(lo) else "N/A"
        print(f"  {cfg_i['label']:18s} vs {cfg_j['label']:18s}  τ={tau_str}  CI={ci_str}")

    # 4. Self-judge bias
    bias_scores = compute_self_judge_bias(judge_ranks, ref_judge_key="gpt4omini")

    # 5. CSV 저장
    # 5-A: 랭킹 테이블
    ranking_csv = DATA_DIR / "results_self_judge_bias.csv"
    all_models_set = set(m for r in judge_ranks.values() for m in r)
    with open(ranking_csv, "w", newline="") as f:
        writer = csv.writer(f)
        header = ["model_id", "family"] + [
            next(c["label"] for c in JUDGE_CONFIGS if c["key"] == k)
            for k in available_keys
        ] + [
            f"bias_{k}" for k in available_keys if k in bias_scores
        ]
        writer.writerow(header)
        for model in sorted(all_models_set):
            row = [model, EVAL_MODEL_FAMILY.get(model, "other")]
            for k in available_keys:
                row.append(judge_ranks[k].get(model, ""))
            for k in available_keys:
                if k in bias_scores:
                    row.append(f"{bias_scores[k].get(model, 0.0):.3f}")
            writer.writerow(row)
    print(f"\n[OK] 랭킹 CSV: {ranking_csv}")

    # 5-B: Kendall τ matrix
    tau_csv = DATA_DIR / "results_kendall_tau_matrix.csv"
    with open(tau_csv, "w", newline="") as f:
        writer = csv.writer(f)
        labels = [next(c["label"] for c in JUDGE_CONFIGS if c["key"] == k) for k in available_keys]
        writer.writerow(["judge_a", "judge_b", "tau", "tau_distance", "ci_lower", "ci_upper"])
        for ki, kj in combinations(available_keys, 2):
            tau = tau_matrix.get((ki, kj), float("nan"))
            pt, lo, hi = tau_ci.get((ki, kj), (float("nan"),) * 3)
            la = next(c["label"] for c in JUDGE_CONFIGS if c["key"] == ki)
            lb = next(c["label"] for c in JUDGE_CONFIGS if c["key"] == kj)
            dist = kendall_tau_distance(tau) if not math.isnan(tau) else float("nan")
            writer.writerow([la, lb,
                             f"{tau:.4f}" if not math.isnan(tau) else "",
                             f"{dist:.4f}" if not math.isnan(dist) else "",
                             f"{lo:.4f}" if not math.isnan(lo) else "",
                             f"{hi:.4f}" if not math.isnan(hi) else ""])
    print(f"[OK] Kendall τ matrix CSV: {tau_csv}")

    # 6. Figure
    out_fig = FIGURES_DIR / "fig_self_judge_bias.png"
    plot_self_judge_bias(
        JUDGE_CONFIGS, judge_grades, judge_ranks,
        tau_matrix, bias_scores, tau_ci, out_fig,
    )

    # 7. 콘솔 요약
    print("\n── 랭킹 요약 ──────────────────────────────────────────")
    all_models_sorted = sorted(
        all_models_set,
        key=lambda m: judge_ranks.get("gpt4omini", judge_ranks[available_keys[0]]).get(m, 99)
    )
    header_line = f"{'모델':<35}" + "".join(
        f"{next(c['label'] for c in JUDGE_CONFIGS if c['key'] == k):>12}"
        for k in available_keys
    )
    print(header_line)
    print("-" * len(header_line))
    for m in all_models_sorted:
        family_mark = " ◀" if EVAL_MODEL_FAMILY.get(m) != "other" else ""
        line = f"{m:<35}" + "".join(
            f"{judge_ranks[k].get(m, '-'):>12}" for k in available_keys
        ) + family_mark
        print(line)

    print("\n── Kendall τ distance 요약 (낮을수록 랭킹 일치) ─────")
    for (ki, kj), tau in tau_matrix.items():
        if not math.isnan(tau):
            cfg_i = next(c for c in JUDGE_CONFIGS if c["key"] == ki)
            cfg_j = next(c for c in JUDGE_CONFIGS if c["key"] == kj)
            same_family = "★ same-family" if cfg_i["family"] == cfg_j["family"] else ""
            print(f"  {cfg_i['label']:18s} ↔ {cfg_j['label']:18s}  "
                  f"τ={tau:.3f}  dist={kendall_tau_distance(tau):.3f}  {same_family}")


if __name__ == "__main__":
    main()
