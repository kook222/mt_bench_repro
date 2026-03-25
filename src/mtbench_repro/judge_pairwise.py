# src/mtbench_repro/judge_pairwise.py
"""
MT-Bench Pairwise comparison 수행 (논문 Figure 5, 9, Section 3.1, 3.4).

왜 swap을 두 번 하는가:
- 논문 Section 3.3: LLM judge는 position bias가 있어 먼저 나온 답변을 선호한다.
  GPT-4도 65% consistency (Table 2) — 35%는 순서만 바꿔도 판정이 달라진다.
- 논문 Section 3.4 conservative approach:
  AB 순서와 BA 순서에서 모두 같은 결과가 나올 때만 winner 선언.
  불일치 시 "inconsistent" → aggregate에서 tie로 처리.

Multi-turn 프롬프트 (Figure 9) 사용 이유:
- 논문 Section 3.5: 두 turn을 분리하면 judge가 이전 답변을 잘못 참조한다.
  전체 대화 컨텍스트를 하나의 프롬프트에 담아 2nd turn에 집중하게 한다.
"""

from __future__ import annotations

import argparse
import itertools
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from mtbench_repro.client import ChatClient
from mtbench_repro.io_utils import (
    append_jsonl,
    get_answer_path,
    get_processed_ids,
    load_answers,
    load_questions,
)
from mtbench_repro.prompts import (
    build_multiturn_pairwise_prompt,
    parse_pairwise_verdict,
    resolve_pairwise_winner,
)
from mtbench_repro.schemas import JudgmentPairwise, ModelAnswer, MTBenchQuestion

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 단일 문항 pairwise 판정 (swap 포함)
# ---------------------------------------------------------------------------

def judge_pairwise_question(
    question: MTBenchQuestion,
    answer_a: ModelAnswer,
    answer_b: ModelAnswer,
    judge_client: ChatClient,
    judge_model: str = "gpt-4",
) -> JudgmentPairwise:
    """
    한 질문에 대해 두 모델의 답변을 비교 판정. AB/BA 순서로 각 1회 호출.

    Multi-turn 프롬프트(Figure 9) 사용:
    - 2-turn 전체 대화를 하나의 프롬프트에 담는다.
    - 논문 Section 3.5에서 이 방식이 turn별 분리보다 정확하다고 검증됨.

    Conservative verdict 결정:
    - AB 판정과 BA 판정이 일치 → 해당 모델 ID를 winner로 기록
    - 불일치 → "inconsistent" (aggregate에서 tie로 취급)

    Args:
        question: MTBenchQuestion
        answer_a: 첫 번째 모델 답변
        answer_b: 두 번째 모델 답변
        judge_client: ChatClient 인스턴스
        judge_model: judge 모델명

    Returns:
        JudgmentPairwise 인스턴스
    """
    turns_q = question.turns
    turns_a = answer_a.get_turns()
    turns_b = answer_b.get_turns()

    # ── AB 순서 판정 (model_a가 Assistant A 역할) ──
    msgs_ab = build_multiturn_pairwise_prompt(
        turns=turns_q,
        answers_a=turns_a,
        answers_b=turns_b,
    )
    raw_ab = judge_client.chat(
        messages=msgs_ab,
        model=judge_model,
        temperature=0.0,
        max_tokens=1024,
    )
    verdict_ab = parse_pairwise_verdict(raw_ab)

    # ── BA 순서 판정 (model_b가 Assistant A 역할) ──
    # swap: answers_a와 answers_b를 뒤집어 전달
    msgs_ba = build_multiturn_pairwise_prompt(
        turns=turns_q,
        answers_a=turns_b,   # model_b를 A 자리에
        answers_b=turns_a,   # model_a를 B 자리에
    )
    raw_ba = judge_client.chat(
        messages=msgs_ba,
        model=judge_model,
        temperature=0.0,
        max_tokens=1024,
    )
    verdict_ba = parse_pairwise_verdict(raw_ba)

    # BA 판정을 원래 모델 기준으로 정규화해 conservative winner 계산
    winner = resolve_pairwise_winner(
        verdict_ab=verdict_ab,
        verdict_ba=verdict_ba,
        model_a=answer_a.model_id,
        model_b=answer_b.model_id,
    )

    if verdict_ab == "error" or verdict_ba == "error":
        logger.warning(
            f"Pairwise parse error: question_id={question.question_id}, "
            f"AB='{raw_ab[:80]}', BA='{raw_ba[:80]}'"
        )

    return JudgmentPairwise(
        question_id=question.question_id,
        model_a=answer_a.model_id,
        model_b=answer_b.model_id,
        judge_id=judge_model,
        winner=winner,
        judgment_ab=raw_ab,
        judgment_ba=raw_ba,
        winner_ab=verdict_ab,
        winner_ba=verdict_ba,
        turn=2,              # 논문: multi-turn judge는 2nd turn 기준
        category=question.category,
        tstamp=time.time(),
    )


# ---------------------------------------------------------------------------
# 전체 실행 함수
# ---------------------------------------------------------------------------

def run_judge_pairwise(
    questions_path: str,
    answers_dir: str,
    output_dir: str,
    model_a_id: str,
    model_b_id: str,
    judge_client: ChatClient,
    judge_model: str = "gpt-4",
    sleep_between_calls: float = 2.0,
    resume: bool = True,
) -> None:
    """
    두 모델 간 pairwise comparison을 전체 MT-Bench 질문에 대해 수행.

    출력 경로 규칙:
    - {output_dir}/pairwise/{model_a}_vs_{model_b}.jsonl
    - 파일명이 길어지는 문제를 방지하기 위해 '/'는 '_'로 치환.

    재실행 안전성:
    - question_id 기반 resume: 이미 처리된 question_id는 skip.
    - swap 두 번 호출이므로 sleep_between_calls 기본값을 2.0초로 설정.

    Args:
        questions_path: mt_bench_questions.jsonl 경로
        answers_dir: 모델 답변 JSONL 디렉토리
        output_dir: 판정 결과 저장 디렉토리
        model_a_id: 첫 번째 모델 ID
        model_b_id: 두 번째 모델 ID
        judge_client: ChatClient 인스턴스
        judge_model: judge 모델명
        sleep_between_calls: API 호출 간 대기 (초, swap 2회 포함)
        resume: True면 이미 처리된 question_id skip
    """
    questions = load_questions(questions_path)

    answers_a = load_answers(get_answer_path(answers_dir, model_a_id))
    answers_b = load_answers(get_answer_path(answers_dir, model_b_id))

    safe_a = model_a_id.replace("/", "_")
    safe_b = model_b_id.replace("/", "_")
    output_path = Path(output_dir) / "pairwise" / f"{safe_a}_vs_{safe_b}.jsonl"

    if not resume and output_path.exists():
        output_path.unlink()
        logger.info(f"no-resume: removed existing {output_path}")

    processed_ids = get_processed_ids(output_path) if resume else set()

    pending = [
        q for q in questions
        if q.question_id not in processed_ids
        and q.question_id in answers_a
        and q.question_id in answers_b
    ]

    logger.info(
        f"Pairwise | {model_a_id} vs {model_b_id} | "
        f"judge={judge_model} | pending={len(pending)}"
    )

    for i, question in enumerate(pending, start=1):
        logger.info(
            f"[{i}/{len(pending)}] question_id={question.question_id}, "
            f"category={question.category}"
        )
        try:
            judgment = judge_pairwise_question(
                question=question,
                answer_a=answers_a[question.question_id],
                answer_b=answers_b[question.question_id],
                judge_client=judge_client,
                judge_model=judge_model,
            )
            append_jsonl(output_path, judgment.to_dict())
        except Exception as e:
            logger.error(
                f"Failed pairwise for question_id={question.question_id}: {e}"
            )

        if sleep_between_calls > 0:
            time.sleep(sleep_between_calls)

    logger.info(f"Pairwise complete. Output: {output_path}")


def run_all_pairs(
    questions_path: str,
    answers_dir: str,
    output_dir: str,
    model_ids: List[str],
    judge_client: ChatClient,
    judge_model: str = "gpt-4",
    sleep_between_calls: float = 2.0,
    resume: bool = True,
) -> None:
    """
    모델 목록에서 가능한 모든 pairs에 대해 pairwise comparison 실행.

    논문 Section 4.1: 6개 모델 × 5 pairs = 15쌍을 모두 비교.
    combinations(model_ids, 2)로 중복 없이 순서 없는 쌍을 생성.

    Args:
        model_ids: 비교할 모델 ID 리스트
        나머지 파라미터: run_judge_pairwise와 동일
    """
    pairs = list(itertools.combinations(model_ids, 2))
    logger.info(f"Running {len(pairs)} model pairs.")

    for model_a, model_b in pairs:
        logger.info(f"Pair: {model_a} vs {model_b}")
        run_judge_pairwise(
            questions_path=questions_path,
            answers_dir=answers_dir,
            output_dir=output_dir,
            model_a_id=model_a,
            model_b_id=model_b,
            judge_client=judge_client,
            judge_model=judge_model,
            sleep_between_calls=sleep_between_calls,
            resume=resume,
        )


# ---------------------------------------------------------------------------
# CLI 엔트리포인트
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MT-Bench Pairwise Judge")
    parser.add_argument("--questions", type=str, default="data/mt_bench_questions.jsonl")
    parser.add_argument("--answers-dir", type=str, default="data/answers/")
    parser.add_argument("--output-dir", type=str, default="data/judgments/")
    parser.add_argument("--model-a", type=str, default=None,
                        help="첫 번째 모델 ID (--models와 상호 배타적)")
    parser.add_argument("--model-b", type=str, default=None,
                        help="두 번째 모델 ID")
    parser.add_argument("--models", type=str, nargs="+", default=None,
                        help="모든 pairs를 실행할 모델 목록")
    parser.add_argument("--judge-model", type=str, default="gpt-4")
    parser.add_argument("--openai-api-key", type=str, default=None)
    parser.add_argument("--openai-base-url", type=str,
                        default="https://api.openai.com/v1")
    parser.add_argument("--sleep", type=float, default=2.0)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.mock:
        client = ChatClient.mock()
    else:
        client = ChatClient(
            api_key=args.openai_api_key,
            base_url=args.openai_base_url,
            default_model=args.judge_model,
        )

    if args.models:
        run_all_pairs(
            questions_path=args.questions,
            answers_dir=args.answers_dir,
            output_dir=args.output_dir,
            model_ids=args.models,
            judge_client=client,
            judge_model=args.judge_model,
            sleep_between_calls=args.sleep,
            resume=not args.no_resume,
        )
    elif args.model_a and args.model_b:
        run_judge_pairwise(
            questions_path=args.questions,
            answers_dir=args.answers_dir,
            output_dir=args.output_dir,
            model_a_id=args.model_a,
            model_b_id=args.model_b,
            judge_client=client,
            judge_model=args.judge_model,
            sleep_between_calls=args.sleep,
            resume=not args.no_resume,
        )
    else:
        raise ValueError("--model-a/--model-b 또는 --models 중 하나를 지정해야 합니다.")


if __name__ == "__main__":
    main()