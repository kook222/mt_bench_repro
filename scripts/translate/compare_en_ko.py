#!/usr/bin/env python3
"""
scripts/translate/compare_en_ko.py

영어-한국어 실험 결과 비교 분석 (Phase 2).

방법론:
  80문항 전수 관측 → 서술적 통계만 보고. 가설 검정·효과 크기 없음.

  [분석 1] Inconsistency & Position Bias — EN vs KO
    - judge별 EN/KO inconsistency 비율, 1st-pos bias 비율, Δ

  [분석 2] 카테고리별 EN-KO Score Gap
    - 사전 정의된 8개 카테고리별 Δ = KO − EN 평균 점수
    - 선택 편향 없는 pre-specified 분석

사용법:
    export PYTHONPATH=src
    python3 scripts/translate/compare_en_ko.py

출력:
    data/ko/results/results_en_ko_comparison.csv
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

DATA_EN = PROJECT_ROOT / "data" / "en"
DATA_KO = PROJECT_ROOT / "data" / "ko"

JUDGE_LABELS = ["qwen_7B", "qwen_14B", "qwen_32B", "exaone_32B", "gpt4omini"]

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

MT_BENCH_CATEGORIES = [
    "writing", "roleplay", "reasoning", "math",
    "coding", "extraction", "stem", "humanities",
]


# ── 데이터 로드 ───────────────────────────────────────────────────────────────

def load_question_categories() -> Dict[int, str]:
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


def load_per_question_scores(single_dir: Path) -> Dict[str, Dict[int, float]]:
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


# ── 분석 1: Inconsistency & Position Bias ────────────────────────────────────

def analyze_inconsistency(judges: List[str]) -> List[Dict]:
    rows = []
    print("\n" + "=" * 70)
    print("[분석 1] Inconsistency & 1st-pos Bias — EN vs KO")
    print("=" * 70)

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
            continue

        en_ip = ei / et * 100 if et else float("nan")
        en_fp = ef / et * 100 if et else float("nan")
        ko_ip = ki / kt * 100 if kt else float("nan")
        ko_fp = kf / kt * 100 if kt else float("nan")

        print(f"\n  {JUDGE_DISPLAY[jlabel]}")
        print(f"    Inconsistency : EN {en_ip:5.1f}%  KO {ko_ip:5.1f}%  Δ={ko_ip-en_ip:+.1f}%p")
        print(f"    1st-pos bias  : EN {en_fp:5.1f}%  KO {ko_fp:5.1f}%  Δ={ko_fp-en_fp:+.1f}%p")

        rows.append({
            "judge": jlabel,
            "en_incon_pct": round(en_ip, 2),
            "ko_incon_pct": round(ko_ip, 2),
            "delta_incon_pct": round(ko_ip - en_ip, 2),
            "en_fp_pct": round(en_fp, 2),
            "ko_fp_pct": round(ko_fp, 2),
            "delta_fp_pct": round(ko_fp - en_fp, 2),
        })

    return rows


# ── 분석 2: 카테고리별 EN-KO Score Gap ───────────────────────────────────────

def analyze_category_gap(judges: List[str], primary_judge: str = "qwen_32B") -> List[Dict]:
    cat_map = load_question_categories()
    rows = []

    print("\n" + "=" * 70)
    print("[분석 2] 카테고리별 EN-KO Score Gap (pre-specified 8 categories)")
    print(f"  기준 judge: {JUDGE_DISPLAY.get(primary_judge, primary_judge)}")
    print("=" * 70)
    print(f"  {'Category':<14} {'EN mean':>9} {'KO mean':>9} {'Δ (KO-EN)':>11} {'n_pairs':>8}")
    print("-" * 70)

    for jlabel in [primary_judge] + [j for j in judges if j != primary_judge]:
        en_dir, ko_dir = SINGLE_DIRS[jlabel]
        en_pq = load_per_question_scores(en_dir)
        ko_pq = load_per_question_scores(ko_dir)
        if not en_pq or not ko_pq:
            continue

        if jlabel == primary_judge:
            print(f"\n  [{JUDGE_DISPLAY[jlabel]}]")

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

            if not en_vals:
                continue

            en_mean = float(np.mean(en_vals))
            ko_mean = float(np.mean(ko_vals))
            delta = ko_mean - en_mean

            if jlabel == primary_judge:
                print(f"  {cat:<14} {en_mean:>9.3f} {ko_mean:>9.3f} {delta:>+11.3f} {len(en_vals):>8}")

            rows.append({
                "judge": jlabel,
                "category": cat,
                "en_mean": round(en_mean, 4),
                "ko_mean": round(ko_mean, 4),
                "delta": round(delta, 4),
                "n_pairs": len(en_vals),
            })

    return rows


# ── CSV 저장 ─────────────────────────────────────────────────────────────────

def save_csv(incon_rows: List[Dict], cat_rows: List[Dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        writer.writerow(["## 분석1: Inconsistency & Position Bias"])
        dw = csv.DictWriter(f, fieldnames=[
            "judge",
            "en_incon_pct", "ko_incon_pct", "delta_incon_pct",
            "en_fp_pct", "ko_fp_pct", "delta_fp_pct",
        ], extrasaction="ignore")
        dw.writeheader()
        dw.writerows(incon_rows)

        writer.writerow([])
        writer.writerow(["## 분석2: 카테고리별 EN-KO Score Gap"])
        dw = csv.DictWriter(f, fieldnames=[
            "judge", "category", "en_mean", "ko_mean", "delta", "n_pairs",
        ], extrasaction="ignore")
        dw.writeheader()
        dw.writerows(cat_rows)

    print(f"\n[저장] {output_path}")


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    available = [j for j in JUDGE_LABELS
                 if PAIRWISE_DIRS[j][0].exists() and PAIRWISE_DIRS[j][1].exists()]
    if not available:
        print("[오류] 데이터 없음")
        sys.exit(1)

    print(f"실행 judge: {[JUDGE_DISPLAY[j] for j in available]}")

    incon_rows = analyze_inconsistency(available)
    cat_rows   = analyze_category_gap(available, primary_judge="qwen_32B")

    save_csv(incon_rows, cat_rows, DATA_KO / "results" / "results_en_ko_comparison.csv")
    print("완료.")


if __name__ == "__main__":
    main()
