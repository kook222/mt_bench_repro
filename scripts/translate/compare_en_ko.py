#!/usr/bin/env python3
"""
scripts/translate/compare_en_ko.py

영어-한국어 실험 결과 비교 분석 (Phase 2).

비교 항목 3개:
  [비교 1] Judge Scaling + 모델 랭킹 상관관계 (EN vs KO)
    - 각 judge별 EN 모델 순위와 KO 모델 순위의 Spearman ρ
    - 높은 ρ → 같은 judge가 두 언어에서 모델을 동일하게 평가

  [비교 2] Inconsistency & Position Bias (EN vs KO 비교)
    - 각 judge별 EN/KO inconsistency 비율 및 1st-pos bias 비율
    - KO에서 inconsistency가 낮아지는 구조적 원인 정량화

  [비교 3] Top-Disc 문항 기반 랭킹 상관관계
    - EN에서 모델 간 판별력이 높은 Top-20 문항 선별
    - 해당 문항 기준 EN/KO 랭킹 Spearman ρ
    - 높은 ρ → 번역이 변별력 구조를 보존

사용법:
    export PYTHONPATH=src
    python3 scripts/translate/compare_en_ko.py
    python3 scripts/translate/compare_en_ko.py --judge qwen_32B
    python3 scripts/translate/compare_en_ko.py --topdisc-n 20 --ref-judge qwen_32B

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

# ── 유틸리티 ──────────────────────────────────────────────────────────────────

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
    for f in single_dir.glob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
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
            avg = sum(valid) / len(valid)
            result.setdefault(model, {})[qid] = avg
    return result


def rank_models(scores: Dict[str, float]) -> List[str]:
    """전체 점수 내림차순 정렬 → 모델 리스트"""
    return sorted(scores, key=lambda m: scores[m], reverse=True)


def spearman_rho(rank_a: List[str], rank_b: List[str]) -> Optional[float]:
    """두 순위 리스트의 Spearman ρ (공통 모델만 사용)."""
    common = [m for m in rank_a if m in rank_b]
    n = len(common)
    if n < 3:
        return None
    pos_a = {m: i for i, m in enumerate(rank_a)}
    pos_b = {m: i for i, m in enumerate(rank_b)}
    d2 = sum((pos_a[m] - pos_b[m]) ** 2 for m in common)
    return 1 - 6 * d2 / (n * (n * n - 1))


def load_pairwise_stats(pairwise_dir: Path) -> Tuple[int, int, int]:
    """pairwise JSONL → (total, n_inconsistent, n_first_pos_bias)"""
    total = incon = fp = 0
    if not pairwise_dir.exists():
        return 0, 0, 0
    for f in pairwise_dir.glob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            total += 1
            if r.get("winner") == "inconsistent":
                incon += 1
                if r.get("winner_ab") == "A" and r.get("winner_ba") == "A":
                    fp += 1
    return total, incon, fp


def fmt_rho(v: Optional[float]) -> str:
    return f"{v:.4f}" if v is not None else "N/A"


# ── 비교 1: Judge Scaling + 랭킹 상관관계 ────────────────────────────────────

def compare_scaling(judges: List[str]) -> List[Dict]:
    rows = []
    print("\n" + "=" * 75)
    print("[비교 1] Judge별 EN/KO 모델 랭킹 상관관계 (Spearman ρ)")
    print("=" * 75)
    print(f"  {'Judge':<15} {'EN Top-3':<30} {'KO Top-3':<30} {'ρ':>8}")
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
        rho = spearman_rho(en_rank, ko_rank)

        def short(m: str) -> str:
            parts = m.split("-")
            return parts[0] if len(parts[0]) > 3 else "-".join(parts[:2])

        en_top = " > ".join(short(m) for m in en_rank[:3])
        ko_top = " > ".join(short(m) for m in ko_rank[:3])
        print(f"  {JUDGE_DISPLAY[jlabel]:<15} {en_top:<30} {ko_top:<30} {fmt_rho(rho):>8}")
        rows.append({
            "judge": jlabel,
            "en_rank": ">".join(en_rank),
            "ko_rank": ">".join(ko_rank),
            "spearman_rho_overall": rho,
        })

    return rows


# ── 비교 2: Inconsistency & Position Bias ────────────────────────────────────

def compare_position_bias(judges: List[str]) -> List[Dict]:
    rows = []
    print("\n" + "=" * 75)
    print("[비교 2] Inconsistency & 1st-pos Bias — EN vs KO")
    print("=" * 75)
    print(f"  {'Judge':<15} {'EN Incon':>10} {'KO Incon':>10} {'Δ(KO-EN)':>10}"
          f" {'EN 1stpos':>10} {'KO 1stpos':>10}")
    print("-" * 75)

    for jlabel in judges:
        en_dir, ko_dir = PAIRWISE_DIRS[jlabel]
        et, ei, ef = load_pairwise_stats(en_dir)
        kt, ki, kf = load_pairwise_stats(ko_dir)

        if et == 0 and kt == 0:
            print(f"  {JUDGE_DISPLAY[jlabel]:<15}  (pairwise 없음)")
            continue

        en_ip = ei / et * 100 if et else float("nan")
        ko_ip = ki / kt * 100 if kt else float("nan")
        delta = ko_ip - en_ip
        en_fp = ef / et * 100 if et else float("nan")
        ko_fp = kf / kt * 100 if kt else float("nan")

        print(
            f"  {JUDGE_DISPLAY[jlabel]:<15}"
            f" {en_ip:>9.1f}%"
            f" {ko_ip:>9.1f}%"
            f" {delta:>+9.1f}%p"
            f" {en_fp:>9.1f}%"
            f" {ko_fp:>9.1f}%"
        )
        rows.append({
            "judge": jlabel,
            "en_total": et, "en_incon": ei, "en_incon_pct": round(en_ip, 2),
            "en_fp": ef, "en_fp_pct": round(en_fp, 2),
            "ko_total": kt, "ko_incon": ki, "ko_incon_pct": round(ko_ip, 2),
            "ko_fp": kf, "ko_fp_pct": round(ko_fp, 2),
            "delta_incon_pct": round(delta, 2),
        })

    return rows


# ── 비교 3: Top-Disc 문항 기반 랭킹 상관관계 ─────────────────────────────────

def get_topdisc_questions(ref_judge: str, n: int = 20) -> List[int]:
    """
    EN single_grade 결과에서 모델 간 점수 분산이 가장 높은 top-N 문항 ID 반환.
    높은 분산 = 모델을 잘 변별하는 문항.
    """
    en_dir, _ = SINGLE_DIRS[ref_judge]
    per_q: Dict[int, List[float]] = {}
    for f in en_dir.glob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            qid = r.get("question_id")
            s1, s2 = r.get("score_turn1"), r.get("score_turn2")
            valid = [s for s in (s1, s2) if s is not None and s != -1.0]
            if not valid or qid is None:
                continue
            per_q.setdefault(qid, []).append(sum(valid) / len(valid))

    def variance(vals: List[float]) -> float:
        if len(vals) < 2:
            return 0.0
        mean = sum(vals) / len(vals)
        return sum((v - mean) ** 2 for v in vals) / len(vals)

    ranked = sorted(per_q, key=lambda q: variance(per_q[q]), reverse=True)
    return ranked[:n]


def compare_topdisc(
    judges: List[str],
    ref_judge: str = "qwen_32B",
    n: int = 20,
) -> List[Dict]:
    """Top-N 변별 문항 기준 EN/KO 모델 랭킹 Spearman ρ."""
    top_qids = get_topdisc_questions(ref_judge, n)

    print(f"\n{'=' * 75}")
    print(f"[비교 3] Top-{n} 변별 문항 기준 EN/KO 랭킹 Spearman ρ")
    print(f"  기준 judge: {JUDGE_DISPLAY.get(ref_judge, ref_judge)}")
    print(f"  Top-{n} 문항 ID: {sorted(top_qids)}")
    print("=" * 75)
    print(f"  {'Judge':<15} {'ρ (Top-Disc)':>14} {'ρ (전체)':>12}")
    print("-" * 75)

    rows = []
    for jlabel in judges:
        en_dir, ko_dir = SINGLE_DIRS[jlabel]
        en_all = load_per_question_scores(en_dir)
        ko_all = load_per_question_scores(ko_dir)
        if not en_all or not ko_all:
            print(f"  {JUDGE_DISPLAY[jlabel]:<15}  (single_grade 없음)")
            continue

        def avg_on_qids(per_q: Dict[str, Dict[int, float]], qids: List[int]) -> Dict[str, float]:
            result = {}
            for model, q_scores in per_q.items():
                vals = [q_scores[q] for q in qids if q in q_scores]
                if vals:
                    result[model] = sum(vals) / len(vals)
            return result

        en_td_scores = avg_on_qids(en_all, top_qids)
        ko_td_scores = avg_on_qids(ko_all, top_qids)
        rho_td = spearman_rho(rank_models(en_td_scores), rank_models(ko_td_scores))

        en_overall = load_overall_scores(SCORE_FILES[jlabel][0])
        ko_overall = load_overall_scores(SCORE_FILES[jlabel][1])
        rho_all = spearman_rho(rank_models(en_overall), rank_models(ko_overall))

        print(f"  {JUDGE_DISPLAY[jlabel]:<15} {fmt_rho(rho_td):>14} {fmt_rho(rho_all):>12}")
        rows.append({
            "judge": jlabel,
            "topdisc_n": n,
            "ref_judge": ref_judge,
            "spearman_rho_topdisc": rho_td,
            "spearman_rho_overall": rho_all,
        })

    return rows


# ── CSV 저장 ─────────────────────────────────────────────────────────────────

def save_comparison_csv(
    scaling_rows: List[Dict],
    bias_rows: List[Dict],
    topdisc_rows: List[Dict],
    output_path: Path,
) -> None:
    bias_by_j = {r["judge"]: r for r in bias_rows}
    topdisc_by_j = {r["judge"]: r for r in topdisc_rows}

    fieldnames = [
        "judge",
        "en_rank", "ko_rank", "spearman_rho_overall",
        "en_incon_pct", "ko_incon_pct", "delta_incon_pct",
        "en_fp_pct", "ko_fp_pct",
        "spearman_rho_topdisc",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for sr in scaling_rows:
            row = {k: sr.get(k) for k in fieldnames}
            br = bias_by_j.get(sr["judge"], {})
            tr = topdisc_by_j.get(sr["judge"], {})
            for k in ["en_incon_pct", "ko_incon_pct", "delta_incon_pct", "en_fp_pct", "ko_fp_pct"]:
                row[k] = br.get(k)
            row["spearman_rho_topdisc"] = tr.get("spearman_rho_topdisc")
            writer.writerow(row)
    print(f"\n[저장] {output_path}")


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="EN-KO 비교 분석 (Phase 2)")
    parser.add_argument("--judge", default=None,
                        help=f"judge 필터 ({', '.join(JUDGE_LABELS)})")
    parser.add_argument("--topdisc-n", type=int, default=20,
                        help="Top-Disc 문항 수 (기본 20)")
    parser.add_argument("--ref-judge", default="qwen_32B",
                        help="Top-Disc 선별 기준 judge (기본 qwen_32B)")
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

    print(f"실행 judge: {[JUDGE_DISPLAY[j] for j in available]}")

    scaling_rows = compare_scaling(available)
    bias_rows    = compare_position_bias(available)
    topdisc_rows = compare_topdisc(available, ref_judge=args.ref_judge, n=args.topdisc_n)

    output_csv = DATA_KO / "results" / "results_en_ko_comparison.csv"
    save_comparison_csv(scaling_rows, bias_rows, topdisc_rows, output_csv)

    print("\n완료.")


if __name__ == "__main__":
    main()
