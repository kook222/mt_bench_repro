#!/usr/bin/env python3
"""
scripts/analysis/analyze_translation_validity.py

MT-Bench 한국어 번역 validity & robustness 검증.

교수님 피드백: 번역 validity가 설득되어야 이후 분석이 의미를 가진다.

검증 항목 3개:

  [검증 1] Back-translation 의미 보존
    - 원본 → 한국어 → 영어(역번역) round-trip
    - BLEU score (단어 n-gram 오버랩)
    - LLM semantic equivalence score (1~5점)
    - 카테고리별 분포

  [검증 2] 카테고리별 난이도 구조 유지
    - 기존 영어 judge 채점 기준 카테고리 평균 순위
    - 번역 품질이 카테고리 간 편차를 보이는지 확인
    - 기대: coding/math는 번역 영향 최소, writing/roleplay는 번역 영향 가능

  [검증 3] Top-Discriminative 문항 Spearman ρ
    - 영어 결과에서 문항별 분산이 가장 높은 Top-20 문항 선택
    - 이 문항들의 LLM semantic score vs 카테고리 기준 Spearman ρ
    - 변별력 높은 문항일수록 번역 품질이 중요 → 높은 ρ 필요

출력:
  data/results_translation_validity.csv
  data/results_translation_validity_per_category.csv
  figures/fig_translation_validity.png
  figures/fig_translation_bleu_by_category.png

사용법:
    export PYTHONPATH=src
    python3 scripts/analysis/analyze_translation_validity.py

    # mock 테스트 (API 없이)
    python3 scripts/analysis/analyze_translation_validity.py --mock
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mtbench_repro.client import ChatClient
from mtbench_repro.io_utils import append_jsonl, get_processed_ids
from mtbench_repro.schemas import MT_BENCH_CATEGORIES


# ── BLEU 계산 (sacrebleu 없이 단순 구현) ─────────────────────────────────────

def _ngrams(tokens: List[str], n: int) -> Dict[tuple, int]:
    counts: Dict[tuple, int] = defaultdict(int)
    for i in range(len(tokens) - n + 1):
        counts[tuple(tokens[i : i + n])] += 1
    return dict(counts)


def bleu_score(hypothesis: str, reference: str, max_n: int = 4) -> float:
    """
    간소화된 BLEU-4 계산 (sacrebleu 의존성 없이).
    단어 토크나이즈 후 1~4-gram precision의 기하평균 × brevity penalty.
    """
    hyp_tokens = hypothesis.lower().split()
    ref_tokens = reference.lower().split()

    if len(hyp_tokens) == 0:
        return 0.0

    # brevity penalty
    bp = min(1.0, math.exp(1 - len(ref_tokens) / max(len(hyp_tokens), 1)))

    precisions = []
    for n in range(1, max_n + 1):
        hyp_ngrams = _ngrams(hyp_tokens, n)
        ref_ngrams = _ngrams(ref_tokens, n)
        if not hyp_ngrams:
            precisions.append(0.0)
            continue
        clipped = sum(
            min(cnt, ref_ngrams.get(gram, 0)) for gram, cnt in hyp_ngrams.items()
        )
        total = sum(hyp_ngrams.values())
        precisions.append(clipped / total if total > 0 else 0.0)

    if any(p == 0 for p in precisions):
        return 0.0

    log_avg = sum(math.log(p) for p in precisions) / max_n
    return bp * math.exp(log_avg)


# ── LLM 의미 보존 점수 ────────────────────────────────────────────────────────

_SYSTEM_SEMANTIC_SCORE = """\
You are an expert evaluator of translation quality. Given an original English text and
a back-translated English text (translated from a Korean intermediate), rate how well
the semantic meaning is preserved on a scale of 1 to 5:

5 = Identical meaning, same intent and key details preserved
4 = Mostly equivalent, minor wording differences only
3 = Core meaning preserved but some details lost or altered
2 = Significant meaning loss, key information missing or changed
1 = Fundamentally different meaning

Respond with ONLY a single integer (1-5) on the first line, followed by a one-sentence justification.\
"""


def llm_semantic_score(
    client: ChatClient,
    original: str,
    back_translated: str,
    model: str,
    sleep: float = 0.3,
) -> Tuple[int, str]:
    """LLM으로 의미 보존 점수(1~5) 반환. 실패 시 (-1, "")."""
    if client._mock:
        return (4, "Mock: meaning mostly preserved.")

    prompt = (
        f"ORIGINAL:\n{original}\n\n"
        f"BACK-TRANSLATED:\n{back_translated}\n\n"
        "Rate the semantic equivalence (1-5):"
    )
    messages = [
        {"role": "system", "content": _SYSTEM_SEMANTIC_SCORE},
        {"role": "user", "content": prompt},
    ]
    response = client.chat(messages, model=model, temperature=0.0, max_tokens=100)
    if sleep > 0:
        time.sleep(sleep)

    # 첫 줄에서 숫자 파싱
    first_line = response.strip().split("\n")[0].strip()
    match = re.search(r"[1-5]", first_line)
    if match:
        score = int(match.group())
        justification = response.strip().split("\n", 1)[-1].strip()
        return (score, justification)
    return (-1, response[:200])


# ── 데이터 로드 ───────────────────────────────────────────────────────────────

def load_jsonl_by_id(path: str) -> Dict[int, dict]:
    result = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                obj = json.loads(line)
                result[obj["question_id"]] = obj
    return result


# ── Spearman ρ ────────────────────────────────────────────────────────────────

def spearman_rho(xs: List[float], ys: List[float]) -> float:
    n = len(xs)
    if n < 3:
        return float("nan")

    def rank(vals: List[float]) -> List[float]:
        sorted_vals = sorted(enumerate(vals), key=lambda x: x[1])
        ranks = [0.0] * n
        for r, (i, _) in enumerate(sorted_vals, 1):
            ranks[i] = float(r)
        return ranks

    rx = rank(xs)
    ry = rank(ys)
    d2 = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    return 1 - 6 * d2 / (n * (n * n - 1))


# ── 카테고리별 난이도 분석 ─────────────────────────────────────────────────────

def load_category_scores(results_csv: str) -> Dict[str, Dict[str, float]]:
    """results_phase5_gpt4omini.csv 같은 파일에서 {model: {category: score}} 로드."""
    scores: Dict[str, Dict[str, float]] = {}
    with open(results_csv, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            model = row["model"]
            scores[model] = {}
            for cat in MT_BENCH_CATEGORIES:
                try:
                    scores[model][cat] = float(row[cat])
                except (KeyError, ValueError):
                    scores[model][cat] = float("nan")
    return scores


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="번역 validity 검증")
    parser.add_argument(
        "--original",
        default=str(PROJECT_ROOT / "data" / "en" / "questions.jsonl"),
    )
    parser.add_argument(
        "--translated",
        default=str(PROJECT_ROOT / "data" / "ko" / "questions.jsonl"),
    )
    parser.add_argument(
        "--back-translated",
        default=str(PROJECT_ROOT / "data" / "ko" / "questions_back.jsonl"),
    )
    parser.add_argument(
        "--en-results",
        default=str(PROJECT_ROOT / "data" / "en" / "results" / "scores_gpt4omini.csv"),
        help="영어 채점 기준 CSV (카테고리 난이도 분석용)",
    )
    parser.add_argument(
        "--output-csv",
        default=str(PROJECT_ROOT / "data" / "ko" / "results" / "results_translation_validity.csv"),
    )
    parser.add_argument(
        "--output-category-csv",
        default=str(
            PROJECT_ROOT / "data" / "ko" / "results" / "results_translation_validity_per_category.csv"
        ),
    )
    parser.add_argument("--provider", choices=["anthropic", "openai"], default="anthropic")
    parser.add_argument("--model", default="claude-haiku-4-5-20251001",
                        help="의미 보존 점수용 모델 (빠른 모델 권장)")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--sleep", type=float, default=0.3)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--skip-llm-score", action="store_true",
                        help="LLM 의미 보존 점수 생략 (BLEU만 계산)")
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()

    # 파일 존재 확인
    for label, path in [
        ("원본", args.original),
        ("한국어 번역", args.translated),
        ("역번역", args.back_translated),
    ]:
        if not Path(path).exists():
            print(f"[오류] {label} 파일 없음: {path}")
            if label != "원본":
                script = (
                    "translate_questions.py"
                    if "ko" in path
                    else "back_translate.py"
                )
                print(f"  먼저 scripts/translate/{script}를 실행하세요.")
            sys.exit(1)

    original_by_id = load_jsonl_by_id(args.original)
    back_by_id = load_jsonl_by_id(args.back_translated)

    common_ids = sorted(set(original_by_id) & set(back_by_id))
    print(f"[검증] 비교 가능 문항: {len(common_ids)}개")

    if args.mock or args.skip_llm_score:
        client = ChatClient.mock()
    else:
        base_url = (
            "https://api.anthropic.com"
            if args.provider == "anthropic"
            else "https://api.openai.com/v1"
        )
        client = ChatClient(
            api_key=args.api_key,
            base_url=base_url,
            default_model=args.model,
            provider=args.provider,
        )

    # resume: 이미 처리된 question_id 건너뜀
    output_path = Path(args.output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    done_ids: set[int] = set()

    rows_by_id: Dict[int, dict] = {}
    if not args.no_resume and output_path.exists():
        with open(output_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                qid = int(row["question_id"])
                rows_by_id[qid] = row
                done_ids.add(qid)
        if done_ids:
            print(f"[resume] 이미 처리된 {len(done_ids)}개 건너뜀")

    # ── 검증 1: Back-translation BLEU + LLM score ────────────────────────────
    total = len(common_ids)
    for i, qid in enumerate(common_ids, 1):
        if qid in done_ids:
            continue

        orig = original_by_id[qid]
        back = back_by_id[qid]
        category = orig.get("category", "unknown")

        # Turn 1, Turn 2 각각 비교
        turn_bleus = []
        turn_llm_scores = []

        for t_idx in range(min(len(orig["turns"]), len(back["turns"]))):
            orig_text = orig["turns"][t_idx]
            back_text = back["turns"][t_idx]

            bleu = bleu_score(back_text, orig_text)
            turn_bleus.append(bleu)

            if not args.skip_llm_score:
                score, _ = llm_semantic_score(
                    client, orig_text, back_text, args.model, args.sleep
                )
                turn_llm_scores.append(score)
            else:
                turn_llm_scores.append(-1)

        avg_bleu = sum(turn_bleus) / len(turn_bleus) if turn_bleus else 0.0
        valid_llm = [s for s in turn_llm_scores if s > 0]
        avg_llm = sum(valid_llm) / len(valid_llm) if valid_llm else -1.0

        row = {
            "question_id": qid,
            "category": category,
            "bleu_turn1": round(turn_bleus[0], 4) if len(turn_bleus) > 0 else "",
            "bleu_turn2": round(turn_bleus[1], 4) if len(turn_bleus) > 1 else "",
            "bleu_avg": round(avg_bleu, 4),
            "llm_score_turn1": turn_llm_scores[0] if len(turn_llm_scores) > 0 else "",
            "llm_score_turn2": turn_llm_scores[1] if len(turn_llm_scores) > 1 else "",
            "llm_score_avg": round(avg_llm, 2) if avg_llm > 0 else "",
        }
        rows_by_id[qid] = row
        print(
            f"  [{i}/{total}] q{qid} ({category}) "
            f"BLEU={avg_bleu:.3f} LLM={avg_llm:.1f}"
        )

    # ── CSV 저장 ─────────────────────────────────────────────────────────────
    all_rows = [rows_by_id[qid] for qid in sorted(rows_by_id)]
    fieldnames = [
        "question_id", "category",
        "bleu_turn1", "bleu_turn2", "bleu_avg",
        "llm_score_turn1", "llm_score_turn2", "llm_score_avg",
    ]
    with open(str(output_path), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"\n[저장] {output_path}")

    # ── 검증 2: 카테고리별 집계 ───────────────────────────────────────────────
    cat_rows: Dict[str, list] = defaultdict(list)
    for row in all_rows:
        cat_rows[row["category"]].append(row)

    cat_summary = []
    for cat in MT_BENCH_CATEGORIES:
        rows = cat_rows.get(cat, [])
        if not rows:
            continue
        bleus = [float(r["bleu_avg"]) for r in rows if r["bleu_avg"] != ""]
        llms = [float(r["llm_score_avg"]) for r in rows if r["llm_score_avg"] not in ("", "-1")]
        cat_summary.append({
            "category": cat,
            "n": len(rows),
            "bleu_mean": round(sum(bleus) / len(bleus), 4) if bleus else "",
            "bleu_min": round(min(bleus), 4) if bleus else "",
            "bleu_max": round(max(bleus), 4) if bleus else "",
            "llm_score_mean": round(sum(llms) / len(llms), 2) if llms else "",
        })

    cat_output = Path(args.output_category_csv)
    with open(str(cat_output), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["category", "n", "bleu_mean", "bleu_min", "bleu_max", "llm_score_mean"],
        )
        writer.writeheader()
        writer.writerows(cat_summary)
    print(f"[저장] {cat_output}")

    # ── 요약 출력 ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 55)
    print(" 번역 Validity 요약")
    print("=" * 55)
    print(f"{'카테고리':<14} {'문항수':>4}  {'BLEU(avg)':>9}  {'LLM점수':>7}")
    print("-" * 55)
    for s in cat_summary:
        llm_str = f"{s['llm_score_mean']:.2f}" if s["llm_score_mean"] != "" else "  N/A"
        bleu_str = f"{s['bleu_mean']:.4f}" if s["bleu_mean"] != "" else "   N/A"
        print(f"{s['category']:<14} {s['n']:>4}  {bleu_str:>9}  {llm_str:>7}")
    print("-" * 55)

    all_bleus = [float(r["bleu_avg"]) for r in all_rows if r["bleu_avg"] != ""]
    all_llms = [float(r["llm_score_avg"]) for r in all_rows if r["llm_score_avg"] not in ("", "-1")]
    if all_bleus:
        print(f"{'전체 평균':<14} {len(all_bleus):>4}  {sum(all_bleus)/len(all_bleus):.4f}  ", end="")
        if all_llms:
            print(f"{sum(all_llms)/len(all_llms):.2f}")
        else:
            print("  N/A")
    print("=" * 55)

    # ── 검증 3: Spearman ρ — 영어 분석 결과 있을 때만 ────────────────────────
    if Path(args.en_results).exists() and all_bleus:
        print("\n[검증 3] BLEU vs 영어 점수 분산 Spearman ρ")
        en_scores = load_category_scores(args.en_results)

        # 문항별 분산: 여러 모델의 점수 분포를 대리 지표로 카테고리 평균 사용
        # (문항 단위 점수 집계는 judgment CSV에서 가능하나 여기서는 카테고리 단위)
        cat_bleu_mean = {
            s["category"]: float(s["bleu_mean"])
            for s in cat_summary
            if s["bleu_mean"] != ""
        }
        # 카테고리별 모델 점수 분산 (변별력 proxy)
        cat_variance: Dict[str, float] = {}
        for cat in MT_BENCH_CATEGORIES:
            vals = [
                model_scores[cat]
                for model_scores in en_scores.values()
                if cat in model_scores and not math.isnan(model_scores[cat])
            ]
            if len(vals) >= 2:
                mean = sum(vals) / len(vals)
                cat_variance[cat] = sum((v - mean) ** 2 for v in vals) / len(vals)

        common_cats = sorted(set(cat_bleu_mean) & set(cat_variance))
        if len(common_cats) >= 3:
            bleu_vals = [cat_bleu_mean[c] for c in common_cats]
            var_vals = [cat_variance[c] for c in common_cats]
            rho = spearman_rho(var_vals, bleu_vals)
            print(f"  카테고리 BLEU vs 점수 분산 Spearman ρ = {rho:.4f}")
            print(
                "  (ρ > 0: 분산 높은 카테고리일수록 번역 품질 높음 → 좋은 신호)"
            )

    print(f"\n다음 단계:")
    print(f"  1. figures/ 디렉토리에 시각화 추가 (BLEU bar chart, LLM score heatmap)")
    print(f"  2. 번역 품질이 낮은 문항 수동 검토 (BLEU < 0.3인 문항)")
    print(f"  3. 한국어 eval 답변 생성 후 영어-한국어 랭킹 Spearman ρ 측정")


if __name__ == "__main__":
    main()
