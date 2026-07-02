#!/usr/bin/env python3
"""
scripts/translate/compare_en_ko.py

영어-한국어 실험 결과 비교 분석 (Phase 2).

방법론:
  데이터셋이 80문항 전수 관측이므로 가설 검정(p-value) 없이
  서술적 통계 + 효과 크기(Cohen's dz)로 보고한다.

  [분석 1] Per-question EN-KO Score Correlation (Spearman ρ)
    - 각 (judge, model) 쌍에 대해 EN 80문항 점수 vs KO 80문항 점수의 Spearman ρ
    - 전수 관측이므로 ρ 자체가 기술 통계량; p-value 없음
    - 참고: Fu & Liu (EMNLP 2025), Zheng et al. (NeurIPS 2023)

  [분석 2] 모델 랭킹 상관관계 (Spearman ρ)
    - judge별 EN 모델 순위 vs KO 모델 순위의 Spearman ρ (n=6)
    - 전수 관측 기술 통계; p-value 없음

  [분석 3] Inconsistency & Position Bias
    - judge별 EN/KO inconsistency·1st-pos bias 비율 및 Δ
    - 전수 판정 결과이므로 비율 자체가 모수; p-value 없음

  [분석 4] 카테고리별 EN-KO Score Gap (Cohen's dz)
    - 사전 정의된 8개 카테고리별 Δ = KO - EN 점수 차이
    - 효과 크기: Cohen's dz = Δ / SD(diffs)  (small<0.2, medium<0.5, large≥0.5)
    - 선택 편향 없는 pre-specified 분석

사용법:
    export PYTHONPATH=src
    python3 scripts/translate/compare_en_ko.py
    python3 scripts/translate/compare_en_ko.py --judge qwen_32B

출력:
    data/ko/results/results_en_ko_comparison.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

DATA_EN = PROJECT_ROOT / "data" / "en"
DATA_KO = PROJECT_ROOT / "data" / "ko"

# ── 파일 경로 매핑 ────────────────────────────────────────────────────────────
JUDGE_LABELS = ["qwen_7B", "qwen_14B", "qwen_32B", "exaone_32B", "gpt4omini"]

SCORE_FILES: Dict[str, Tuple[Path, Path]] = {
    "qwen_7B":    (DATA_EN / "results" / "results_phase3_judge_7B.csv",
                   DATA_KO / "results" / "results_ko_judge_7B.csv"),
    "qwen_14B":   (DATA_EN / "results" / "results_phase3_judge_14B.csv",
                   DATA_KO / "results" / "results_ko_judge_14B.csv"),
    "qwen_32B":   (DATA_EN / "results" / "results_phase3_judge_32B.csv",
                   DATA_KO / "results" / "results_ko_judge_32B.csv"),
    "exaone_32B": (DATA_EN / "results" / "results_phase3_judge_exaone32B.csv",
                   DATA_KO / "results" / "results_ko_judge_exaone32B.csv"),
    "gpt4omini":  (DATA_EN / "results" / "results_en_judge_gpt4omini.csv",
                   DATA_KO / "results" / "results_ko_judge_gpt4omini.csv"),
}

PAIRWISE_DIRS: Dict[str, Tuple[Path, Path]] = {
    "qwen_7B":    (DATA_EN / "judgments" / "qwen"   / "judge_7B"        / "pairwise",
                   DATA_KO / "judgments" / "qwen"   / "judge_7B"        / "pairwise"),
    "qwen_14B":   (DATA_EN / "judgments" / "qwen"   / "judge_14B"       / "pairwise",
                   DATA_KO / "judgments" / "qwen"   / "judge_14B"       / "pairwise"),
    "qwen_32B":   (DATA_EN / "judgments" / "qwen"   / "judge_32B"       / "pairwise",
                   DATA_KO / "judgments" / "qwen"   / "judge_32B"       / "pairwise"),
    "exaone_32B": (DATA_EN / "judgments" / "exaone" / "judge_32B"       / "pairwise",
                   DATA_KO / "judgments" / "exaone" / "judge_32B"       / "pairwise"),
    "gpt4omini":  (DATA_EN / "judgments" / "gpt"    / "judge_gpt4omini" / "pairwise",
                   DATA_KO / "judgments" / "gpt"    / "judge_gpt4omini" / "pairwise"),
}

SINGLE_DIRS: Dict[str, Tuple[Path, Path]] = {
    "qwen_7B":    (DATA_EN / "judgments" / "qwen"   / "judge_7B"        / "single_grade",
                   DATA_KO / "judgments" / "qwen"   / "judge_7B"        / "single_grade"),
    "qwen_14B":   (DATA_EN / "judgments" / "qwen"   / "judge_14B"       / "single_grade",
                   DATA_KO / "judgments" / "qwen"   / "judge_14B"       / "single_grade"),
    "qwen_32B":   (DATA_EN / "judgments" / "qwen"   / "judge_32B"       / "single_grade",
                   DATA_KO / "judgments" / "qwen"   / "judge_32B"       / "single_grade"),
    "exaone_32B": (DATA_EN / "judgments" / "exaone" / "judge_32B"       / "single_grade",
                   DATA_KO / "judgments" / "exaone" / "judge_32B"       / "single_grade"),
    "gpt4omini":  (DATA_EN / "judgments" / "gpt"    / "judge_gpt4omini" / "single_grade",
                   DATA_KO / "judgments" / "gpt"    / "judge_gpt4omini" / "single_grade"),
}

JUDGE_DISPLAY = {
    "qwen_7B": "Qwen-7B", "qwen_14B": "Qwen-14B", "qwen_32B": "Qwen-32B",
    "exaone_32B": "EXAONE-32B", "gpt4omini": "GPT-4o-mini",
}

# 8개 MT-Bench 카테고리 (사전 정의, 데이터 기반 선별 아님)
MT_BENCH_CATEGORIES = [
    "writing", "roleplay", "reasoning", "math",
    "coding", "extraction", "stem", "humanities",
]


# ── 유틸리티 ──────────────────────────────────────────────────────────────────

def load_question_categories() -> Dict[int, str]:
    """questions.jsonl → {question_id: category}"""
    q_path = DATA_KO / "questions.jsonl"
    if not q_path.exists():
        q_path = DATA_EN / "questions.jsonl"
    cat_map: Dict[int, str] = {}
    if not q_path.exists():
        return cat_map
    for line in q_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            cat_map[r["question_id"]] = r["category"]
    return cat_map


def load_overall_scores(csv_path: Path) -> Dict[str, float]:
    """results CSV → {model: overall_score}"""
    scores: Dict[str, float] = {}
    if not csv_path.exists():
        return scores
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                scores[row["model"]] = float(row["overall"])
            except (KeyError, ValueError):
                pass
    return scores


def load_per_question_scores(
    single_dir: Path,
) -> Dict[str, Dict[int, float]]:
    """single_grade JSONL → {model: {question_id: avg_score}}"""
    result: Dict[str, Dict[int, float]] = {}
    if not single_dir.exists():
        return result
    seen_stems: set = set()
    for fpath in sorted(single_dir.glob("*.jsonl")):
        stem = fpath.stem.split(" ")[0]
        if stem in seen_stems:
            continue
        seen_stems.add(stem)
        try:
            with open(fpath, encoding="utf-8") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    r = json.loads(line)
                    model = r.get("model_id", "")
                    qid = r.get("question_id")
                    s1 = r.get("score_turn1")
                    s2 = r.get("score_turn2")
                    valid = [s for s in (s1, s2) if s is not None and s != -1.0]
                    if not valid or qid is None:
                        continue
                    result.setdefault(model, {})[qid] = sum(valid) / len(valid)
        except OSError:
            pass
    return result


def rank_models(scores: Dict[str, float]) -> List[str]:
    return sorted(scores, key=lambda m: scores[m], reverse=True)


def spearman_rho_manual(rank_a: List[str], rank_b: List[str]) -> Optional[float]:
    """n=6 순위 Spearman ρ (공통 모델만)."""
    common = [m for m in rank_a if m in rank_b]
    n = len(common)
    if n < 3:
        return None
    pos_a = {m: i for i, m in enumerate(rank_a)}
    pos_b = {m: i for i, m in enumerate(rank_b)}
    d2 = sum((pos_a[m] - pos_b[m]) ** 2 for m in common)
    return 1 - 6 * d2 / (n * (n * n - 1))


def cohens_dz(diffs: List[float]) -> float:
    """paired Cohen's dz = mean(diffs) / SD(diffs)."""
    if len(diffs) < 2:
        return float("nan")
    arr = np.array(diffs, dtype=float)
    sd = float(np.std(arr, ddof=1))
    if sd == 0:
        return float("nan")
    return float(np.mean(arr) / sd)


def effect_label(dz: float) -> str:
    """Cohen's dz 크기 해석 (절댓값 기준)."""
    if np.isnan(dz):
        return "N/A"
    a = abs(dz)
    if a < 0.2:
        return "negligible"
    if a < 0.5:
        return "small"
    if a < 0.8:
        return "medium"
    return "large"


def fmt(v: Optional[float], decimals: int = 4) -> str:
    return f"{v:.{decimals}f}" if v is not None else "N/A"


# ── 분석 1: Per-question Score Correlation ───────────────────────────────────

def analyze_score_correlation(judges: List[str]) -> List[Dict]:
    """
    각 (judge, model)에 대해 EN vs KO 80문항 점수의 Spearman ρ.
    전수 관측이므로 ρ 자체를 기술 통계량으로 보고; p-value 없음.
    """
    rows = []
    print("\n" + "=" * 75)
    print("[분석 1] Per-question EN-KO Score Correlation (Spearman ρ, n=80)")
    print("  ρ: 문항 수준에서 EN-KO 점수 패턴 보존 정도 (전수 관측, p-value 없음)")
    print("=" * 75)
    print(f"  {'Judge':<15} {'Model':<35} {'ρ':>7}")
    print("-" * 75)

    for jlabel in judges:
        en_dir, ko_dir = SINGLE_DIRS[jlabel]
        en_pq = load_per_question_scores(en_dir)
        ko_pq = load_per_question_scores(ko_dir)
        if not en_pq or not ko_pq:
            print(f"  {JUDGE_DISPLAY[jlabel]:<15}  (데이터 없음)")
            continue

        common_models = [m for m in en_pq if m in ko_pq]
        rhos = []
        for model in sorted(common_models):
            en_q = en_pq[model]
            ko_q = ko_pq[model]
            common_qids = sorted(set(en_q) & set(ko_q))
            if len(common_qids) < 10:
                continue
            en_vec = np.array([en_q[q] for q in common_qids], dtype=float)
            ko_vec = np.array([ko_q[q] for q in common_qids], dtype=float)
            # Spearman ρ via rank correlation (no scipy)
            en_rank = np.argsort(np.argsort(en_vec)).astype(float)
            ko_rank = np.argsort(np.argsort(ko_vec)).astype(float)
            n = len(en_rank)
            d2 = float(np.sum((en_rank - ko_rank) ** 2))
            rho = 1 - 6 * d2 / (n * (n * n - 1))
            rhos.append(rho)
            print(f"  {JUDGE_DISPLAY[jlabel]:<15} {model:<35} {rho:>7.4f}")

        if rhos:
            mean_rho = float(np.mean(rhos))
            sd_rho = float(np.std(rhos, ddof=1)) if len(rhos) > 1 else float("nan")
            print(f"  {'':15} {'  → mean ρ (SD)':35} {mean_rho:>7.4f}  (SD={sd_rho:.4f})")
            rows.append({
                "judge": jlabel,
                "mean_perq_rho": round(mean_rho, 4),
                "sd_perq_rho": round(sd_rho, 4),
                "n_models": len(rhos),
            })
        print()

    return rows


# ── 분석 2: 모델 랭킹 Spearman ρ ─────────────────────────────────────────────

def analyze_ranking_correlation(judges: List[str]) -> List[Dict]:
    """
    judge별 EN/KO 모델 랭킹 Spearman ρ (n=6).
    전수 관측이므로 p-value 없이 ρ만 보고.
    """
    rows = []
    print("\n" + "=" * 75)
    print("[분석 2] 모델 랭킹 Spearman ρ (n=6, 기술 통계, p-value 없음)")
    print("=" * 75)
    print(f"  {'Judge':<15} {'EN Top-3':<30} {'KO Top-3':<30} {'ρ':>6}")
    print("-" * 75)

    for jlabel in judges:
        en_path, ko_path = SCORE_FILES[jlabel]
        en_scores = load_overall_scores(en_path)
        ko_scores = load_overall_scores(ko_path)
        if not en_scores or not ko_scores:
            print(f"  {JUDGE_DISPLAY[jlabel]:<15}  (데이터 없음)")
            continue

        en_rank = rank_models(en_scores)
        ko_rank = rank_models(ko_scores)
        rho = spearman_rho_manual(en_rank, ko_rank)

        def short(m: str) -> str:
            parts = m.split("-")
            return parts[0] if len(parts[0]) > 3 else "-".join(parts[:2])

        en_top = " > ".join(short(m) for m in en_rank[:3])
        ko_top = " > ".join(short(m) for m in ko_rank[:3])
        print(
            f"  {JUDGE_DISPLAY[jlabel]:<15} {en_top:<30} {ko_top:<30}"
            f" {rho:>6.3f}"
        )
        rows.append({
            "judge": jlabel,
            "en_rank": ">".join(en_rank),
            "ko_rank": ">".join(ko_rank),
            "spearman_rho_ranking": round(rho, 4) if rho is not None else None,
        })

    return rows


# ── 분석 3: Inconsistency & Position Bias ────────────────────────────────────

def analyze_inconsistency(judges: List[str]) -> List[Dict]:
    """
    judge별 EN/KO inconsistency·1st-pos bias 비율 및 Δ.
    전수 판정 결과이므로 비율 자체가 모수; p-value 없음.
    """
    rows = []
    print("\n" + "=" * 75)
    print("[분석 3] Inconsistency & 1st-pos Bias — EN vs KO (기술 통계)")
    print("=" * 75)

    for jlabel in judges:
        en_dir, ko_dir = PAIRWISE_DIRS[jlabel]

        def load_stats(d: Path) -> Tuple[int, int, int]:
            total = incon = fp = 0
            if not d.exists():
                return 0, 0, 0
            for fpath in sorted(d.glob("*.jsonl")):
                try:
                    with open(fpath, encoding="utf-8") as fh:
                        for line in fh:
                            if not line.strip():
                                continue
                            r = json.loads(line)
                            total += 1
                            if r.get("winner") == "inconsistent":
                                incon += 1
                                if r.get("winner_ab") == "A" and r.get("winner_ba") == "A":
                                    fp += 1
                except OSError:
                    pass
            return total, incon, fp

        et, ei, ef = load_stats(en_dir)
        kt, ki, kf = load_stats(ko_dir)

        if et == 0 and kt == 0:
            print(f"  {JUDGE_DISPLAY[jlabel]}  (pairwise 없음)")
            continue

        en_ip = ei / et * 100 if et else float("nan")
        en_fp = ef / et * 100 if et else float("nan")
        ko_ip = ki / kt * 100 if kt else float("nan")
        ko_fp = kf / kt * 100 if kt else float("nan")

        d_ip = ko_ip - en_ip
        d_fp = ko_fp - en_fp

        print(f"\n  {JUDGE_DISPLAY[jlabel]}")
        print(f"    Inconsistency:  EN {en_ip:5.1f}%  KO {ko_ip:5.1f}%  Δ={d_ip:+.1f}%p")
        print(f"    1st-pos bias:   EN {en_fp:5.1f}%  KO {ko_fp:5.1f}%  Δ={d_fp:+.1f}%p")

        rows.append({
            "judge": jlabel,
            "en_total": et, "en_incon": ei, "en_incon_pct": round(en_ip, 2),
            "ko_total": kt, "ko_incon": ki, "ko_incon_pct": round(ko_ip, 2),
            "delta_incon_pct": round(d_ip, 2),
            "en_fp": ef, "en_fp_pct": round(en_fp, 2),
            "ko_fp": kf, "ko_fp_pct": round(ko_fp, 2),
            "delta_fp_pct": round(d_fp, 2),
        })

    return rows


# ── 분석 4: 카테고리별 EN-KO Score Gap ───────────────────────────────────────

def analyze_category_gap(judges: List[str], primary_judge: str = "qwen_32B") -> List[Dict]:
    """
    사전 정의된 8개 카테고리별 EN-KO 평균 점수 차이 + Cohen's dz.
    전수 관측이므로 가설 검정 없이 효과 크기로 보고.
    """
    cat_map = load_question_categories()

    rows = []
    print("\n" + "=" * 75)
    print("[분석 4] 카테고리별 EN-KO Score Gap (pre-specified 8 categories)")
    print(f"  효과 크기: Cohen's dz (paired, model×question) — {JUDGE_DISPLAY.get(primary_judge, primary_judge)} 기준")
    print("  기준: |dz| < 0.2 negligible, 0.2–0.5 small, 0.5–0.8 medium, ≥0.8 large")
    print("=" * 75)
    print(f"  {'Category':<14} {'EN mean':>9} {'KO mean':>9} {'Δ (KO-EN)':>11}"
          f" {'n_pairs':>8} {'dz':>8} {'effect':>10}")
    print("-" * 75)

    for jlabel in [primary_judge] + [j for j in judges if j != primary_judge]:
        en_dir, ko_dir = SINGLE_DIRS[jlabel]
        en_pq = load_per_question_scores(en_dir)
        ko_pq = load_per_question_scores(ko_dir)
        if not en_pq or not ko_pq:
            continue

        if jlabel == primary_judge:
            print(f"\n  [{JUDGE_DISPLAY[jlabel]}]")

        judge_rows = []
        for cat in MT_BENCH_CATEGORIES:
            cat_qids = [qid for qid, c in cat_map.items() if c == cat]
            en_vals, ko_vals = [], []
            for model in en_pq:
                if model not in ko_pq:
                    continue
                for qid in cat_qids:
                    if qid in en_pq[model] and qid in ko_pq[model]:
                        en_vals.append(en_pq[model][qid])
                        ko_vals.append(ko_pq[model][qid])

            if len(en_vals) < 4:
                continue

            diffs = [k - e for k, e in zip(ko_vals, en_vals)]
            en_mean = float(np.mean(en_vals))
            ko_mean = float(np.mean(ko_vals))
            delta = ko_mean - en_mean
            dz = cohens_dz(diffs)
            eff = effect_label(dz)

            if jlabel == primary_judge:
                print(f"  {cat:<14} {en_mean:>9.3f} {ko_mean:>9.3f} {delta:>+11.3f}"
                      f" {len(en_vals):>8} {dz:>8.3f} {eff:>10}")

            judge_rows.append({
                "judge": jlabel,
                "category": cat,
                "en_mean": round(en_mean, 4),
                "ko_mean": round(ko_mean, 4),
                "delta": round(delta, 4),
                "n_pairs": len(en_vals),
                "cohens_dz": round(dz, 4),
                "effect_size": eff,
            })

        rows.extend(judge_rows)

    return rows


# ── CSV 저장 ─────────────────────────────────────────────────────────────────

def save_comparison_csv(
    corr_rows: List[Dict],
    rank_rows: List[Dict],
    incon_rows: List[Dict],
    cat_rows: List[Dict],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    section1_fields = ["judge", "mean_perq_rho", "sd_perq_rho", "n_models"]
    section2_fields = ["judge", "en_rank", "ko_rank", "spearman_rho_ranking"]
    section3_fields = [
        "judge",
        "en_incon_pct", "ko_incon_pct", "delta_incon_pct",
        "en_fp_pct", "ko_fp_pct", "delta_fp_pct",
    ]
    section4_fields = [
        "judge", "category", "en_mean", "ko_mean", "delta",
        "n_pairs", "cohens_dz", "effect_size",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        writer.writerow(["## 분석1: Per-question Score Correlation (Spearman rho, p-value 없음)"])
        dw = csv.DictWriter(f, fieldnames=section1_fields, extrasaction="ignore")
        dw.writeheader()
        dw.writerows(corr_rows)

        writer.writerow([])
        writer.writerow(["## 분석2: 모델 랭킹 Spearman rho (p-value 없음)"])
        dw = csv.DictWriter(f, fieldnames=section2_fields, extrasaction="ignore")
        dw.writeheader()
        dw.writerows(rank_rows)

        writer.writerow([])
        writer.writerow(["## 분석3: Inconsistency & Position Bias (p-value 없음)"])
        dw = csv.DictWriter(f, fieldnames=section3_fields, extrasaction="ignore")
        dw.writeheader()
        dw.writerows(incon_rows)

        writer.writerow([])
        writer.writerow(["## 분석4: 카테고리별 EN-KO Score Gap (Cohen's dz)"])
        dw = csv.DictWriter(f, fieldnames=section4_fields, extrasaction="ignore")
        dw.writeheader()
        dw.writerows(cat_rows)

    print(f"\n[저장] {output_path}")


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="EN-KO 비교 분석 (Phase 2)")
    parser.add_argument("--judge", default=None,
                        help=f"judge 필터 ({', '.join(JUDGE_LABELS)})")
    parser.add_argument("--primary-judge", default="qwen_32B",
                        help="카테고리 분석 상세 출력 기준 judge (기본 qwen_32B)")
    args = parser.parse_args()

    judges = JUDGE_LABELS if args.judge is None else [args.judge]
    unknown = [j for j in judges if j not in JUDGE_LABELS]
    if unknown:
        print(f"[오류] 알 수 없는 judge: {unknown}  가능: {JUDGE_LABELS}")
        sys.exit(1)

    available = [j for j in judges
                 if SCORE_FILES[j][0].exists() and SCORE_FILES[j][1].exists()]
    skipped = [j for j in judges if j not in available]
    if skipped:
        print(f"[경고] 데이터 없음 (건너뜀): {[JUDGE_DISPLAY[j] for j in skipped]}")
    if not available:
        print("[오류] 실행 가능한 judge가 없습니다.")
        sys.exit(1)

    primary = args.primary_judge if args.primary_judge in available else available[0]
    print(f"실행 judge: {[JUDGE_DISPLAY[j] for j in available]}")
    print(f"카테고리 분석 primary judge: {JUDGE_DISPLAY[primary]}")

    corr_rows  = analyze_score_correlation(available)
    rank_rows  = analyze_ranking_correlation(available)
    incon_rows = analyze_inconsistency(available)
    cat_rows   = analyze_category_gap(available, primary_judge=primary)

    output_csv = DATA_KO / "results" / "results_en_ko_comparison.csv"
    save_comparison_csv(corr_rows, rank_rows, incon_rows, cat_rows, output_csv)
    print("\n완료.")


if __name__ == "__main__":
    main()
