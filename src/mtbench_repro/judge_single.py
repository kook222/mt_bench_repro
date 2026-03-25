# src/mtbench_repro/judge_single.py
"""
MT-Bench Single-answer grading 수행 (논문 Figure 6, Section 3.1).

왜 single-answer grading인가:
- 논문 Table 8의 MT-Bench Score는 GPT-4 single-answer grading 기반.
  각 turn을 독립적으로 1~10점 채점하고 평균을 낸다.
- pairwise보다 scalable: 모델 수 증가 시 pairs가 O(n^2) 이지만
  single grading은 O(n)으로 처리 가능 (논문 Section 3.1 언급).
- 논문 Section 4.2: GPT-4 single grading은 pairwise와 85% 이상 일치.

각 turn을 별도 호출하는 이유:
- 논문 Section 3.5: 2nd turn 채점 시 전체 대화 컨텍스트가 필요하지만,
  단순 single grading에서는 turn별 독립 점수가 Figure 6 기준에 더 맞다.
- aggregate.py에서 turn1/turn2를 분리 분석할 수 있게 두 점수를 모두 저장.
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
from mtbench_repro.prompts import build_multiturn_single_prompt, build_single_prompt, parse_single_score
from mtbench_repro.schemas import JudgmentSingle, ModelAnswer, MTBenchQuestion

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 단일 문항 채점
# ---------------------------------------------------------------------------

def grade_single_question(
    question: MTBenchQuestion,
    answer: ModelAnswer,
    judge_client: ChatClient,
    judge_model: str = "gpt-4",
) -> JudgmentSingle:
    """
    하나의 질문-답변 쌍에 대해 turn별 단일 채점을 수행.

    채점 방식:
    - turn1: 1st turn 질문 + 1st turn 답변 → judge가 1~10점 부여
    - turn2: 2nd turn 질문 + 2nd turn 답변 → judge가 1~10점 부여
    - 각 turn을 독립 호출하는 이유: 논문 Figure 6 프롬프트가
      단일 질문-답변 쌍 기준으로 설계되어 있기 때문.

    파싱 실패 시 score=-1.0으로 저장하고 원문은 보존:
    - 집계 시 -1.0 항목은 제외되고 실패율이 별도 추적된다.
    - 원문(judgment_turn1/2)이 있으면 수동 확인 후 재파싱 가능.

    Args:
        question: MTBenchQuestion
        answer: 채점 대상 ModelAnswer
        judge_client: ChatClient (GPT-4 또는 mock)
        judge_model: judge로 사용할 모델명

    Returns:
        JudgmentSingle 인스턴스
    """
    turns_q = question.turns          # 질문 [q1, q2]
    turns_a = answer.get_turns()      # 답변 [a1, a2]

    # turn1 채점
    msgs_t1 = build_single_prompt(
        question=turns_q[0],
        answer=turns_a[0],
    )
    judgment_t1 = judge_client.chat(
        messages=msgs_t1,
        model=judge_model,
        temperature=0.0,   # judge는 결정론적 판정을 위해 greedy
        max_tokens=512,
    )
    score_t1 = parse_single_score(judgment_t1)

    # turn2 채점 — 전체 대화 컨텍스트 포함 (논문 Figure 10 방식)
    # FastChat 원본: turn2 채점 시 [q1, a1, q2, a2] 전체를 judge에게 제공해야
    # 1st turn 맥락을 고려한 정확한 채점이 가능하다.
    # build_single_prompt(question=turns_q[1], answer=turns_a[1])처럼
    # 2nd turn만 전달하면 judge가 context 없이 a2만 보고 채점하므로 부정확하다.
    msgs_t2 = build_multiturn_single_prompt(
        turns=turns_q,
        answers=turns_a,
    )
    judgment_t2 = judge_client.chat(
        messages=msgs_t2,
        model=judge_model,
        temperature=0.0,
        max_tokens=512,
    )
    score_t2 = parse_single_score(judgment_t2)

    if score_t1 < 0:
        logger.warning(
            f"Score parsing failed for question_id={question.question_id}, "
            f"turn=1. Raw: {judgment_t1[:100]}"
        )
    if score_t2 < 0:
        logger.warning(
            f"Score parsing failed for question_id={question.question_id}, "
            f"turn=2. Raw: {judgment_t2[:100]}"
        )

    return JudgmentSingle(
        question_id=question.question_id,
        model_id=answer.model_id,
        judge_id=judge_model,
        score_turn1=score_t1,
        score_turn2=score_t2,
        judgment_turn1=judgment_t1,
        judgment_turn2=judgment_t2,
        category=question.category,
        tstamp=time.time(),
    )


# ---------------------------------------------------------------------------
# 전체 실행 함수
# ---------------------------------------------------------------------------

def run_judge_single(
    questions_path: str,
    answers_dir: str,
    output_dir: str,
    model_id: str,
    judge_client: ChatClient,
    judge_model: str = "gpt-4",
    sleep_between_calls: float = 1.0,
    resume: bool = True,
) -> None:
    """
    단일 모델에 대해 전체 MT-Bench single-answer grading 수행.

    출력 경로 규칙:
    - {output_dir}/single_grade/{model_id}.jsonl
    - model_id의 '/'는 '_'로 치환해 경로 안전성 확보.

    Args:
        questions_path: mt_bench_questions.jsonl 경로
        answers_dir: 모델 답변 JSONL 디렉토리
        output_dir: 판정 결과 저장 디렉토리
        model_id: 채점 대상 모델 ID
        judge_client: ChatClient 인스턴스
        judge_model: judge 모델명 (기본: gpt-4)
        sleep_between_calls: API 호출 간 대기 (초)
        resume: True면 이미 처리된 question_id skip
    """
    questions = load_questions(questions_path)
    answer_path = get_answer_path(answers_dir, model_id)
    answers: Dict[int, ModelAnswer] = load_answers(answer_path)

    safe_model = model_id.replace("/", "_")
    output_path = Path(output_dir) / "single_grade" / f"{safe_model}.jsonl"

    if not resume and output_path.exists():
        output_path.unlink()
        logger.info(f"no-resume: removed existing {output_path}")

    processed_ids = get_processed_ids(output_path) if resume else set()
    if processed_ids:
        logger.info(f"Resume: skipping {len(processed_ids)} already graded questions.")

    pending = [
        q for q in questions
        if q.question_id not in processed_ids and q.question_id in answers
    ]

    missing = [q.question_id for q in questions if q.question_id not in answers]
    if missing:
        logger.warning(f"No answers found for question_ids: {missing}")

    logger.info(
        f"Single grading | model={model_id}, judge={judge_model}, "
        f"pending={len(pending)}"
    )

    for i, question in enumerate(pending, start=1):
        logger.info(
            f"[{i}/{len(pending)}] Grading question_id={question.question_id}, "
            f"category={question.category}"
        )
        try:
            judgment = grade_single_question(
                question=question,
                answer=answers[question.question_id],
                judge_client=judge_client,
                judge_model=judge_model,
            )
            append_jsonl(output_path, judgment.to_dict())
        except Exception as e:
            logger.error(
                f"Failed to grade question_id={question.question_id}: {e}"
            )

        if sleep_between_calls > 0:
            time.sleep(sleep_between_calls)

    logger.info(f"Single grading complete. Output: {output_path}")


# ---------------------------------------------------------------------------
# CLI 엔트리포인트
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MT-Bench Single-answer Grading")
    parser.add_argument("--questions", type=str, default="data/mt_bench_questions.jsonl")
    parser.add_argument("--answers-dir", type=str, default="data/answers/")
    parser.add_argument("--output-dir", type=str, default="data/judgments/")
    parser.add_argument("--model-id", type=str, required=True,
                        help="채점 대상 모델 ID")
    parser.add_argument("--judge-model", type=str, default="gpt-4",
                        help="judge 모델명")
    parser.add_argument("--openai-api-key", type=str, default=None)
    parser.add_argument("--openai-base-url", type=str,
                        default="https://api.openai.com/v1")
    parser.add_argument("--sleep", type=float, default=1.0)
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

    run_judge_single(
        questions_path=args.questions,
        answers_dir=args.answers_dir,
        output_dir=args.output_dir,
        model_id=args.model_id,
        judge_client=client,
        judge_model=args.judge_model,
        sleep_between_calls=args.sleep,
        resume=not args.no_resume,
    )


if __name__ == "__main__":
    main()