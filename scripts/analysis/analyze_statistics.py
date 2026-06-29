#!/usr/bin/env python3
"""
scripts/analysis/analyze_statistics.py

Permutation test 기반 통계 검정.

분석 항목:
  [1] EN vs KO 점수 차이 — 모델 × judge별 permutation test
  [2] Judge size별 inconsistency — permutation test (7B↔14B, 14B↔32B, EN vs KO)
  [3] Reference vs Non-reference 점수 차이 — permutation test (turn2 기준)

출력:
  data/ko/results/results_stat_en_ko_diff.csv
  data/ko/results/results_stat_inconsistency.csv
  data/ko/results/results_stat_ref_vs_nonref.csv

사용법:
    export PYTHONPATH=src
    python3 scripts/analysis/analyze_statistics.py
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

DATA = PROJECT_ROOT / "data"
OUT  = DATA / "ko" / "results"

JUDGES = ["judge_7B", "judge_14B", "judge_32B"]
MODELS = [
    "EXAONE-3.5-7.8B-Instruct",
    "EEVE-Korean-Instruct-10.8B",
    "Llama-3.1-8B-Instruct",
    "gemma-2-9b-it",
    "Mistral-7B-Instruct-v0.3",
    "Phi-3.5-mini-Instruct",
]
N_PERM = 10_000
RNG    = np.random.default_rng(42)


# ── 통계 함수 ──────────────────────────────────────────────────────────────────

def permutation_test(
    a: List[float],
    b: List[float],
    n_perm: int = N_PERM,
    alternative: str = "two-sided",
) -> Tuple[float, float]:
    """(observed_diff = mean(a)-mean(b), p-value) 반환."""
    a, b = np.array(a, dtype=float), np.array(b, dtype=float)
    obs = a.mean() - b.mean()
    combined = np.concatenate([a, b])
    na = len(a)
    null = np.array([
        (lambda p: p[:na].mean() - p[na:].mean())(RNG.permutation(combined))
        for _ in range(n_perm)
    ])
    if alternative == "two-sided":
        p = float(np.mean(np.abs(null) >= abs(obs)))
    elif alternative == "greater":
        p = float(np.mean(null >= obs))
    else:
        p = float(np.mean(null <= obs))
    return float(obs), p


def sig_label(p: float) -> str:
    if p < 0.001: return "p<0.001"
    if p < 0.01:  return "p<0.01"
    if p < 0.05:  return "p<0.05"
    return f"p={p:.3f} (ns)"


# ── JSONL 로더 ────────────────────────────────────────────────────────────────

def load_single_scores(lang: str, judge: str, model: str) -> Dict[int, Tuple[float, float]]:
    """question_id → (score_turn1, score_turn2). 파싱 실패(-1.0) 제외."""
    path = DATA / lang / "judgments" / "qwen" / judge / "single_grade" / f"{model}.jsonl"
    if not path.exists():
        return {}
    result = {}
    with open(path) as f:
        for line in f:
            d = json.loads(line)
            s1 = d.get("score_turn1", -1.0)
            s2 = d.get("score_turn2", -1.0)
            result[d["question_id"]] = (s1, s2)
    return result


def load_ref_scores(lang: str, judge: str, model: str) -> Dict[int, float]:
    """question_id → score_turn2 (reference-guided, turn2만). 파싱 실패 제외."""
    path = DATA / lang / "judgments" / "qwen" / judge / "single_grade_ref" / f"{model}.jsonl"
    if not path.exists():
        return {}
    result = {}
    with open(path) as f:
        for line in f:
            d = json.loads(line)
            s2 = d.get("score_turn2", -1.0)
            if s2 > 0:
                result[d["question_id"]] = s2
    return result


def load_pairwise_inconsistency(lang: str, judge: str) -> List[int]:
    """pairwise 전체 레코드에서 inconsistency binary (1=inconsistent, 0=consistent) 반환."""
    pw_dir = DATA / lang / "judgments" / "qwen" / judge / "pairwise"
    if not pw_dir.exists():
        return []
    labels = []
    for f in sorted(pw_dir.glob("*.jsonl")):
        with open(f) as fh:
            for line in fh:
                d = json.loads(line)
                labels.append(1 if d.get("winner") == "inconsistent" else 0)
    return labels


# ── 분석 1: EN vs KO 점수 차이 ───────────────────────────────────────────────

def analyze_en_ko_diff() -> List[dict]:
    rows = []
    for judge in JUDGES:
        judge_label = judge.replace("judge_", "Qwen-")
        for model in MODELS:
            en_scores = load_single_scores("en", judge, model)
            ko_scores = load_single_scores("ko", judge, model)

            common_qids = sorted(set(en_scores) & set(ko_scores))
            diffs = []
            for qid in common_qids:
                e1, e2 = en_scores[qid]
                k1, k2 = ko_scores[qid]
                if e1 > 0 and k1 > 0:
                    diffs.append(e1 - k1)
                if e2 > 0 and k2 > 0:
                    diffs.append(e2 - k2)

            if not diffs:
                continue

            mean_d = float(np.mean(diffs))
            # permutation test: diff vs 0 (one-sample → compare diffs to zeros)
            _, p = permutation_test(diffs, [0.0] * len(diffs), alternative="two-sided")
            rows.append({
                "judge": judge_label,
                "model": model,
                "n_samples": len(diffs),
                "mean_diff": round(mean_d, 4),
                "p_value": round(p, 4),
                "sig": sig_label(p),
            })
    return rows


# ── 분석 2: Judge size별 inconsistency permutation test ──────────────────────

def analyze_inconsistency() -> List[dict]:
    rows = []

    for lang in ["en", "ko"]:
        incon_by_judge: Dict[str, List[int]] = {}
        for judge in JUDGES:
            labels = load_pairwise_inconsistency(lang, judge)
            incon_by_judge[judge] = labels

        for judge in JUDGES:
            labels = incon_by_judge[judge]
            if not labels:
                continue
            rows.append({
                "lang": lang.upper(),
                "judge": judge.replace("judge_", "Qwen-"),
                "n_pairs": len(labels),
                "inconsistency_rate": round(float(np.mean(labels)), 4),
                "comparison": "",
                "obs_diff": "",
                "p_value": "",
                "sig": "",
            })

        pairs = [("judge_7B", "judge_14B"), ("judge_14B", "judge_32B"), ("judge_7B", "judge_32B")]
        for j_a, j_b in pairs:
            la = [float(x) for x in incon_by_judge.get(j_a, [])]
            lb = [float(x) for x in incon_by_judge.get(j_b, [])]
            if not la or not lb:
                continue
            obs, p = permutation_test(la, lb, alternative="two-sided")
            rows.append({
                "lang": lang.upper(),
                "judge": f"{j_a.replace('judge_','')} vs {j_b.replace('judge_','')}",
                "n_pairs": f"{len(la)} vs {len(lb)}",
                "inconsistency_rate": "",
                "comparison": "permutation_test",
                "obs_diff": round(obs, 4),
                "p_value": round(p, 4),
                "sig": sig_label(p),
            })

    # EN vs KO 같은 judge permutation test
    for judge in JUDGES:
        la = [float(x) for x in load_pairwise_inconsistency("en", judge)]
        lb = [float(x) for x in load_pairwise_inconsistency("ko", judge)]
        if not la or not lb:
            continue
        obs, p = permutation_test(la, lb, alternative="two-sided")
        rows.append({
            "lang": "EN vs KO",
            "judge": judge.replace("judge_", "Qwen-"),
            "n_pairs": f"{len(la)} vs {len(lb)}",
            "inconsistency_rate": "",
            "comparison": "EN_vs_KO",
            "obs_diff": round(obs, 4),
            "p_value": round(p, 4),
            "sig": sig_label(p),
        })

    return rows


# ── 분석 3: Reference vs Non-reference 점수 차이 ─────────────────────────────

def analyze_ref_vs_nonref() -> List[dict]:
    rows = []
    for lang in ["en", "ko"]:
        for judge in JUDGES:
            judge_label = judge.replace("judge_", "Qwen-")
            nonref_scores: List[float] = []
            ref_scores: List[float]    = []

            for model in MODELS:
                sg = load_single_scores(lang, judge, model)
                for qid, (s1, s2) in sg.items():
                    if s2 > 0:
                        nonref_scores.append(s2)
                ref = load_ref_scores(lang, judge, model)
                for qid, s2 in ref.items():
                    ref_scores.append(s2)

            if not nonref_scores or not ref_scores:
                continue

            obs, p = permutation_test(ref_scores, nonref_scores, alternative="two-sided")
            rows.append({
                "lang": lang.upper(),
                "judge": judge_label,
                "n_nonref": len(nonref_scores),
                "nonref_mean": round(float(np.mean(nonref_scores)), 4),
                "n_ref": len(ref_scores),
                "ref_mean": round(float(np.mean(ref_scores)), 4),
                "diff_ref_minus_nonref": round(obs, 4),
                "p_value": round(p, 4),
                "sig": sig_label(p),
            })

    return rows


# ── 저장 헬퍼 ─────────────────────────────────────────────────────────────────

def save_csv(rows: List[dict], path: Path) -> None:
    if not rows:
        print(f"[skip] 데이터 없음: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"[저장] {path}  ({len(rows)}행)")


# ── 요약 출력 ─────────────────────────────────────────────────────────────────

def print_en_ko_summary(rows: List[dict]) -> None:
    print("\n" + "=" * 65)
    print(" [1] EN vs KO 점수 차이 — Permutation test (Qwen-32B)")
    print("=" * 65)
    print(f"{'모델':<35} {'n':>4}  {'diff':>6}  {'유의'}")
    print("-" * 65)
    for r in rows:
        if r["judge"] != "Qwen-32B":
            continue
        print(f"{r['model']:<35} {r['n_samples']:>4}  {r['mean_diff']:>+6.3f}  {r['sig']}")


def print_inconsistency_summary(rows: List[dict]) -> None:
    print("\n" + "=" * 65)
    print(" [2] Inconsistency — Permutation test")
    print("=" * 65)
    for r in rows:
        if r["comparison"] == "":
            rate = f"{float(r['inconsistency_rate'])*100:.1f}%"
            print(f"  {r['lang']} {r['judge']:<12}  {rate}")
        else:
            print(f"  {r['lang']} {r['judge']:<20}  diff={r['obs_diff']:>+.4f}  {r['sig']}")


def print_ref_summary(rows: List[dict]) -> None:
    print("\n" + "=" * 65)
    print(" [3] Reference vs Non-reference — Permutation test")
    print("=" * 65)
    print(f"{'lang':<4} {'judge':<12}  {'nonref':>7}  {'ref':>7}  {'diff':>6}  {'유의'}")
    print("-" * 65)
    for r in rows:
        print(
            f"{r['lang']:<4} {r['judge']:<12}  "
            f"{r['nonref_mean']:>7.4f}  {r['ref_mean']:>7.4f}  "
            f"{r['diff_ref_minus_nonref']:>+6.4f}  {r['sig']}"
        )


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print("[통계 분석] permutation n_perm=10,000  seed=42")

    print("\n[1/3] EN vs KO 점수 차이 계산 중...")
    diff_rows = analyze_en_ko_diff()
    save_csv(diff_rows, OUT / "results_stat_en_ko_diff.csv")
    print_en_ko_summary(diff_rows)

    print("\n[2/3] Inconsistency permutation test 계산 중...")
    incon_rows = analyze_inconsistency()
    save_csv(incon_rows, OUT / "results_stat_inconsistency.csv")
    print_inconsistency_summary(incon_rows)

    print("\n[3/3] Reference vs Non-reference 점수 차이 계산 중...")
    ref_rows = analyze_ref_vs_nonref()
    save_csv(ref_rows, OUT / "results_stat_ref_vs_nonref.csv")
    print_ref_summary(ref_rows)

    print("\n완료.")


if __name__ == "__main__":
    main()
