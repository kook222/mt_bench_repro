# src/mtbench_repro/judge_reference.py
"""
Reference-guided grading 수행 (논문 Figure 8, 10, Section 3.4).

왜 reference-guided가 필요한가:
- 논문 Section 3.3, Table 4:
  default prompt로 수학 문제를 채점하면 GPT-4도 70% (14/20) 실패.
  reference answer를 제공하면 실패율이 15% (3/20)로 급감.
- LLM은 문제를 독립적으로 풀면 맞히지만, 틀린 답변 컨텍스트에 영향받아
  그 틀린 답변을 옳다고 판정하는 경향이 있다.
- 해결책: reference answer를 judge 프롬프트에 포함해 정답 기준을 제공.

적용 카테고리:
- schemas.REFERENCE_GUIDED_CATEGORIES = ["math", "reasoning", "coding"]
- 나머지 카테고리(writing, roleplay 등)는 주관적이라 reference가 의미 없음.

두 가지 모드:
1. reference-guided pairwise (Figure 8): 두 답변 비교 + reference
2. reference-guided single grading (Figure 10): 단일 채점 + reference
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

from mtbench_repro.client import ChatClient
from mtbench_repro.io_utils import (
    append_jsonl,
    get_answer_path,
    get_processed_ids,
    load_answers,
    load_questions,
)
from mtbench_repro.prompts import (
    build_multiturn_pairwise_reference_prompt,
    build_multiturn_single_prompt,
    parse_pairwise_verdict,
    parse_single_score,
    resolve_pairwise_winner,
)
from mtbench_repro.schemas import (
    JudgmentPairwise,
    JudgmentSingle,
    ModelAnswer,
    MTBenchQuestion,
    REFERENCE_GUIDED_CATEGORIES,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Reference-guided Single Grading (Figure 10)
# ---------------------------------------------------------------------------

def grade_single_with_reference(
    question: MTBenchQuestion,
    answer: ModelAnswer,
    judge_client: ChatClient,
    judge_model: str = "gpt-4",
) -> Optional[JudgmentSingle]:
    """
    Reference answer가 있는 질문에 대해 reference-guided single grading 수행.

    Reference가 없는 경우 None 반환:
    - 모든 질문이 reference를 갖지는 않으므로 호출 측에서 필터링 가능.
    - reference 없는 질문은 judge_single.py에서 처리.

    Multi-turn single grading (Figure 10):
    - 전체 대화 컨텍스트(q1, a1, q2, a2)와 reference(r1, r2)를
      하나의 프롬프트에 담아 2nd turn 답변을 채점.
    - turn1과 turn2를 합쳐 채점하는 방식 사용 (Figure 10 기준).

    Args:
        question: reference 필드가 있는 MTBenchQuestion
        answer: 채점 대상 ModelAnswer
        judge_client: ChatClient 인스턴스
        judge_model: judge 모델명

    Returns:
        JudgmentSingle 또는 None (reference 없는 경우)
    """
    if question.reference is None:
        logger.debug(
            f"No reference for question_id={question.question_id}. Skipping."
        )
        return None

    turns_q = question.turns
    turns_a = answer.get_turns()
    references = question.reference

    # Figure 10: multi-turn reference-guided single grading
    # reference와 함께 전체 대화를 한 번에 채점
    msgs = build_multiturn_single_prompt(
        turns=turns_q,
        answers=turns_a,
        references=references,
    )
    raw_judgment = judge_client.chat(
        messages=msgs,
        model=judge_model,
        temperature=0.0,
        max_tokens=1024,
    )
    # Figure 10은 2nd turn 집중 채점이므로 score_turn2에 저장
    # score_turn1은 -1로 표시해 집계 시 제외 (참고: 이 방식은 논문 설계에 따름)
    score = parse_single_score(raw_judgment)

    if score < 0:
        logger.warning(
            f"Reference-guided score parse failed for "
            f"question_id={question.question_id}. Raw: {raw_judgment[:100]}"
        )

    return JudgmentSingle(
        question_id=question.question_id,
        model_id=answer.model_id,
        judge_id=judge_model,
        score_turn1=-1.0,     # Figure 10은 전체 대화 기준 단일 점수
        score_turn2=score,    # 2nd turn 집중 채점 결과를 turn2에 저장
        judgment_turn1="",
        judgment_turn2=raw_judgment,
        category=question.category,
        tstamp=time.time(),
    )


# ---------------------------------------------------------------------------
# Reference-guided Pairwise (Figure 8)
# ---------------------------------------------------------------------------

def judge_pairwise_with_reference(
    question: MTBenchQuestion,
    answer_a: ModelAnswer,
    answer_b: ModelAnswer,
    judge_client: ChatClient,
    judge_model: str = "gpt-4",
) -> Optional[JudgmentPairwise]:
    """
    Reference answer가 있는 질문에 대해 reference-guided pairwise 판정.

    Figure 8(reference-guided) + Figure 9(multi-turn)를 결합한 프롬프트 사용:
    - reference answer와 두 모델의 전체 2-turn 대화를 하나의 프롬프트에 담음.
    - judge가 reference를 기준으로 전체 대화 맥락에서 정확성을 비교.
    - 2nd turn reference가 있으면 함께 제공하고, 없어도 동작함.

    position bias 완화를 위해 AB/BA swap 수행:
    - 논문 Section 3.4 conservative approach: 두 순서 모두 일치할 때만 winner 선언.

    Args:
        question: reference 필드가 있는 MTBenchQuestion
        answer_a: 첫 번째 모델 답변
        answer_b: 두 번째 모델 답변
        judge_client: ChatClient 인스턴스
        judge_model: judge 모델명

    Returns:
        JudgmentPairwise 또는 None (reference 없는 경우)
    """
    if question.reference is None:
        logger.debug(f"No reference for question_id={question.question_id}.")
        return None

    turns_q = question.turns
    turns_a = answer_a.get_turns()
    turns_b = answer_b.get_turns()
    references = question.reference  # 가용한 모든 reference 사용

    # ── AB 순서 (Figure 8 + Figure 9 결합) ──
    msgs_ab = build_multiturn_pairwise_reference_prompt(
        turns=turns_q,
        answers_a=turns_a,
        answers_b=turns_b,
        references=references,
    )
    raw_ab = judge_client.chat(
        messages=msgs_ab,
        model=judge_model,
        temperature=0.0,
        max_tokens=1024,
    )
    verdict_ab = parse_pairwise_verdict(raw_ab)

    # ── BA 순서 (swap) ──
    msgs_ba = build_multiturn_pairwise_reference_prompt(
        turns=turns_q,
        answers_a=turns_b,   # B를 A 자리에
        answers_b=turns_a,   # A를 B 자리에
        references=references,
    )
    raw_ba = judge_client.chat(
        messages=msgs_ba,
        model=judge_model,
        temperature=0.0,
        max_tokens=1024,
    )
    verdict_ba = parse_pairwise_verdict(raw_ba)

    winner = resolve_pairwise_winner(
        verdict_ab=verdict_ab,
        verdict_ba=verdict_ba,
        model_a=answer_a.model_id,
        model_b=answer_b.model_id,
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
        turn=2,            # multi-turn: 2nd turn 기준
        category=question.category,
        tstamp=time.time(),
    )


# ---------------------------------------------------------------------------
# 전체 실행 함수
# ---------------------------------------------------------------------------

def run_judge_reference_single(
    questions_path: str,
    answers_dir: str,
    output_dir: str,
    model_id: str,
    judge_client: ChatClient,
    judge_model: str = "gpt-4",
    target_categories: Optional[List[str]] = None,
    sleep_between_calls: float = 1.5,
    resume: bool = True,
) -> None:
    """
    Reference-guided single grading을 대상 카테고리 질문에 대해 수행.

    target_categories 기본값:
    - REFERENCE_GUIDED_CATEGORIES = ["math", "reasoning", "coding"]
    - 논문 근거: Section 3.4, Table 4에서 이 카테고리에서 효과 검증됨.

    출력 경로:
    - {output_dir}/single_grade_ref/{model_id}.jsonl
    - 일반 single grading 결과와 분리해 두 방식을 비교 분석할 수 있게 함.

    Args:
        target_categories: reference-guided를 적용할 카테고리 목록.
                           None이면 REFERENCE_GUIDED_CATEGORIES 사용.
    """
    if target_categories is None:
        target_categories = REFERENCE_GUIDED_CATEGORIES

    questions = load_questions(questions_path)
    # reference가 있고 target 카테고리인 질문만 필터링
    ref_questions = [
        q for q in questions
        if q.reference is not None and q.category in target_categories
    ]

    if not ref_questions:
        logger.warning(
            f"No questions with reference found for categories: {target_categories}. "
            "FastChat mt_bench_questions.jsonl에 reference 필드가 있는지 확인하세요."
        )
        return

    answers = load_answers(get_answer_path(answers_dir, model_id))

    safe_model = model_id.replace("/", "_")
    output_path = Path(output_dir) / "single_grade_ref" / f"{safe_model}.jsonl"

    if not resume and output_path.exists():
        output_path.unlink()
        logger.info(f"no-resume: removed existing {output_path}")

    processed_ids = get_processed_ids(output_path) if resume else set()
    pending = [
        q for q in ref_questions
        if q.question_id not in processed_ids and q.question_id in answers
    ]

    logger.info(
        f"Reference-guided single | model={model_id}, judge={judge_model}, "
        f"categories={target_categories}, pending={len(pending)}"
    )

    for i, question in enumerate(pending, start=1):
        logger.info(
            f"[{i}/{len(pending)}] question_id={question.question_id}, "
            f"category={question.category}"
        )
        try:
            judgment = grade_single_with_reference(
                question=question,
                answer=answers[question.question_id],
                judge_client=judge_client,
                judge_model=judge_model,
            )
            if judgment is not None:
                append_jsonl(output_path, judgment.to_dict())
        except Exception as e:
            logger.error(
                f"Failed reference-guided grade for "
                f"question_id={question.question_id}: {e}"
            )

        if sleep_between_calls > 0:
            time.sleep(sleep_between_calls)

    logger.info(f"Reference-guided single grading complete. Output: {output_path}")


def run_judge_reference_pairwise(
    questions_path: str,
    answers_dir: str,
    output_dir: str,
    model_a_id: str,
    model_b_id: str,
    judge_client: ChatClient,
    judge_model: str = "gpt-4",
    target_categories: Optional[List[str]] = None,
    sleep_between_calls: float = 2.0,
    resume: bool = True,
) -> None:
    """
    Reference-guided pairwise를 대상 카테고리 질문에 대해 수행.

    출력 경로:
    - {output_dir}/pairwise_ref/{model_a}_vs_{model_b}.jsonl
    """
    if target_categories is None:
        target_categories = REFERENCE_GUIDED_CATEGORIES

    questions = load_questions(questions_path)
    ref_questions = [
        q for q in questions
        if q.reference is not None and q.category in target_categories
    ]

    if not ref_questions:
        logger.warning("No reference questions found. Exiting.")
        return

    answers_a = load_answers(get_answer_path(answers_dir, model_a_id))
    answers_b = load_answers(get_answer_path(answers_dir, model_b_id))

    safe_a = model_a_id.replace("/", "_")
    safe_b = model_b_id.replace("/", "_")
    output_path = (
        Path(output_dir) / "pairwise_ref" / f"{safe_a}_vs_{safe_b}.jsonl"
    )

    if not resume and output_path.exists():
        output_path.unlink()
        logger.info(f"no-resume: removed existing {output_path}")

    processed_ids = get_processed_ids(output_path) if resume else set()
    pending = [
        q for q in ref_questions
        if q.question_id not in processed_ids
        and q.question_id in answers_a
        and q.question_id in answers_b
    ]

    logger.info(
        f"Reference-guided pairwise | {model_a_id} vs {model_b_id} | "
        f"judge={judge_model} | pending={len(pending)}"
    )

    for i, question in enumerate(pending, start=1):
        logger.info(
            f"[{i}/{len(pending)}] question_id={question.question_id}, "
            f"category={question.category}"
        )
        try:
            judgment = judge_pairwise_with_reference(
                question=question,
                answer_a=answers_a[question.question_id],
                answer_b=answers_b[question.question_id],
                judge_client=judge_client,
                judge_model=judge_model,
            )
            if judgment is not None:
                append_jsonl(output_path, judgment.to_dict())
        except Exception as e:
            logger.error(
                f"Failed reference pairwise for "
                f"question_id={question.question_id}: {e}"
            )

        if sleep_between_calls > 0:
            time.sleep(sleep_between_calls)

    logger.info(f"Reference-guided pairwise complete. Output: {output_path}")


# ---------------------------------------------------------------------------
# CLI 엔트리포인트
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MT-Bench Reference-guided Judge")
    parser.add_argument("--questions", type=str, default="data/mt_bench_questions.jsonl")
    parser.add_argument("--answers-dir", type=str, default="data/answers/")
    parser.add_argument("--output-dir", type=str, default="data/judgments/")
    parser.add_argument("--mode", type=str,
                        choices=["single", "pairwise"], default="single",
                        help="채점 모드: single (Figure 10) 또는 pairwise (Figure 8)")
    parser.add_argument("--model-id", type=str, default=None,
                        help="single 모드: 채점 대상 모델")
    parser.add_argument("--model-a", type=str, default=None,
                        help="pairwise 모드: 첫 번째 모델")
    parser.add_argument("--model-b", type=str, default=None,
                        help="pairwise 모드: 두 번째 모델")
    parser.add_argument("--judge-model", type=str, default="gpt-4")
    parser.add_argument("--categories", type=str, nargs="+",
                        default=None,
                        help="대상 카테고리 (기본: math reasoning coding)")
    parser.add_argument("--openai-api-key", type=str, default=None)
    parser.add_argument("--openai-base-url", type=str,
                        default="https://api.openai.com/v1")
    parser.add_argument("--sleep", type=float, default=1.5)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    client = ChatClient.mock() if args.mock else ChatClient(
        api_key=args.openai_api_key,
        base_url=args.openai_base_url,
        default_model=args.judge_model,
    )

    if args.mode == "single":
        if not args.model_id:
            raise ValueError("single 모드에서는 --model-id가 필요합니다.")
        run_judge_reference_single(
            questions_path=args.questions,
            answers_dir=args.answers_dir,
            output_dir=args.output_dir,
            model_id=args.model_id,
            judge_client=client,
            judge_model=args.judge_model,
            target_categories=args.categories,
            sleep_between_calls=args.sleep,
            resume=not args.no_resume,
        )
    else:
        if not (args.model_a and args.model_b):
            raise ValueError("pairwise 모드에서는 --model-a와 --model-b가 필요합니다.")
        run_judge_reference_pairwise(
            questions_path=args.questions,
            answers_dir=args.answers_dir,
            output_dir=args.output_dir,
            model_a_id=args.model_a,
            model_b_id=args.model_b,
            judge_client=client,
            judge_model=args.judge_model,
            target_categories=args.categories,
            sleep_between_calls=args.sleep,
            resume=not args.no_resume,
        )


if __name__ == "__main__":
    main()