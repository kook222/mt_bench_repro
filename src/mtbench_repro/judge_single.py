"""Run MT-Bench single-answer grading with role-separated v3 prompts.

Turn 1 uses its question-answer pair. Turn 2 uses the full two-turn
conversation and explicitly focuses the judge on the second answer.
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from typing import Dict, List

from mtbench_repro.client import ChatClient
from mtbench_repro.io_utils import (
    get_answer_path,
    get_latest_records,
    load_answers,
    load_questions,
    stable_fingerprint,
    upsert_jsonl,
    write_jsonl_atomic,
)
from mtbench_repro.prompts import build_multiturn_single_prompt, build_single_prompt, parse_single_score
from mtbench_repro.schemas import JudgmentSingle, ModelAnswer, MTBenchQuestion

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def single_input_fingerprint(
    question: MTBenchQuestion,
    answer: ModelAnswer,
    judge_model: str,
    lang: str,
    backend: Dict | None = None,
) -> str:
    turns_q = question.turns
    turns_a = answer.get_turns()
    return stable_fingerprint(
        {
            "protocol": "single-grade-fastchat-role-v3",
            "question_id": question.question_id,
            "category": question.category,
            "judge_model": judge_model,
            "backend": backend or {},
            "turn1_messages": build_single_prompt(
                question=turns_q[0], answer=turns_a[0], lang=lang
            ),
            "turn2_messages": build_multiturn_single_prompt(
                turns=turns_q, answers=turns_a, lang=lang
            ),
        }
    )

def single_record_is_current(
    record: dict,
    question: MTBenchQuestion,
    model_id: str,
    judge_model: str,
    expected_hash: str,
) -> bool:
    """Reject malformed or mismatched single-grade records during resume."""
    def valid_score(value: object) -> bool:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and (value == -1 or 1 <= value <= 10)
        )

    return (
        record.get("question_id") == question.question_id
        and record.get("model_id") == model_id
        and record.get("judge_id") == judge_model
        and record.get("category") == question.category
        and record.get("input_sha256") == expected_hash
        and valid_score(record.get("score_turn1"))
        and valid_score(record.get("score_turn2"))
        and isinstance(record.get("judgment_turn1"), str)
        and bool(record.get("judgment_turn1", "").strip())
        and isinstance(record.get("judgment_turn2"), str)
        and bool(record.get("judgment_turn2", "").strip())
    )

def grade_single_question(
    question: MTBenchQuestion,
    answer: ModelAnswer,
    judge_client: ChatClient,
    judge_model: str = "gpt-4",
    lang: str = "en",
) -> JudgmentSingle:
    """Grade turn 1 alone and turn 2 with the full conversation context."""
    turns_q = question.turns
    turns_a = answer.get_turns()

    msgs_t1 = build_single_prompt(
        question=turns_q[0],
        answer=turns_a[0],
        lang=lang,
    )
    judgment_t1 = judge_client.chat(
        messages=msgs_t1,
        model=judge_model,
        temperature=0.0,
        max_tokens=512,
    )
    score_t1 = parse_single_score(judgment_t1)

    msgs_t2 = build_multiturn_single_prompt(
        turns=turns_q,
        answers=turns_a,
        lang=lang,
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
        input_sha256=single_input_fingerprint(
            question, answer, judge_model, lang, judge_client.fingerprint_identity()
        ),
    )

def run_judge_single(
    questions_path: str,
    answers_dir: str,
    output_dir: str,
    model_id: str,
    judge_client: ChatClient,
    judge_model: str = "gpt-4",
    sleep_between_calls: float = 1.0,
    resume: bool = True,
    lang: str = "en",
    allow_partial: bool = False,
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
        resume: True면 질문·답안·judge prompt fingerprint가 같은 문항만 건너뜀
    """
    questions = load_questions(questions_path)
    answer_path = get_answer_path(answers_dir, model_id)
    answers: Dict[int, ModelAnswer] = load_answers(answer_path)

    safe_model = model_id.replace("/", "_")
    output_path = Path(output_dir) / "single_grade" / f"{safe_model}.jsonl"

    if not resume and output_path.exists():
        output_path.unlink()
        logger.info(f"no-resume: removed existing {output_path}")

    expected_hashes = {
        question.question_id: single_input_fingerprint(
            question,
            answers[question.question_id],
            judge_model,
            lang,
            judge_client.fingerprint_identity(),
        )
        for question in questions
        if question.question_id in answers
    }
    existing_records = get_latest_records(output_path) if resume else {}
    current_records = {
        question.question_id: existing_records[question.question_id]
        for question in questions
        if question.question_id in answers
        and question.question_id in existing_records
        and single_record_is_current(
            existing_records[question.question_id],
            question,
            model_id,
            judge_model,
            expected_hashes[question.question_id],
        )
    }
    if existing_records != current_records:
        write_jsonl_atomic(
            output_path,
            [current_records[qid] for qid in sorted(current_records)],
        )
    pending = [
        question
        for question in questions
        if question.question_id in answers
        and not single_record_is_current(
            current_records.get(question.question_id, {}),
            question,
            model_id,
            judge_model,
            expected_hashes[question.question_id],
        )
    ]

    missing = [q.question_id for q in questions if q.question_id not in answers]
    if missing:
        logger.warning(f"No answers found for question_ids: {missing}")

    logger.info(
        f"Single grading | model={model_id}, judge={judge_model}, "
        f"pending={len(pending)}"
    )

    failed: List[int] = []
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
                lang=lang,
            )
            upsert_jsonl(output_path, judgment.to_dict())
        except Exception as e:
            failed.append(question.question_id)
            logger.error(
                f"Failed to grade question_id={question.question_id}: {e}"
            )

        if sleep_between_calls > 0:
            time.sleep(sleep_between_calls)

    final_records = get_latest_records(output_path)
    invalid = [
        question.question_id
        for question in questions
        if question.question_id in answers
        and not single_record_is_current(
            final_records.get(question.question_id, {}),
            question,
            model_id,
            judge_model,
            expected_hashes[question.question_id],
        )
    ]
    incomplete = sorted(set(missing + failed + invalid))
    valid_final_records = {
        question.question_id: final_records[question.question_id]
        for question in questions
        if question.question_id in answers
        and question.question_id in final_records
        and single_record_is_current(
            final_records[question.question_id],
            question,
            model_id,
            judge_model,
            expected_hashes[question.question_id],
        )
    }
    write_jsonl_atomic(
        output_path,
        [valid_final_records[qid] for qid in sorted(valid_final_records)],
    )
    if incomplete and not allow_partial:
        raise RuntimeError(
            "Single grading incomplete; missing/failed question_ids="
            f"{incomplete}. Partial records were kept for hash-aware resume."
        )
    logger.info(
        "Single grading complete. Output: %s%s",
        output_path,
        f" (partial: {len(incomplete)} missing/failed)" if incomplete else "",
    )

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MT-Bench Single-answer Grading")
    parser.add_argument("--questions", type=str, default="data/en/questions.jsonl")
    parser.add_argument(
        "--answers-dir", type=str, default="runs/reproduction/en/answers/"
    )
    parser.add_argument(
        "--output-dir", type=str, default="runs/reproduction/en/judgments/"
    )
    parser.add_argument("--model-id", type=str, required=True,
                        help="채점 대상 모델 ID")
    parser.add_argument("--judge-model", type=str, default="gpt-4",
                        help="judge 모델명")
    parser.add_argument("--openai-api-key", type=str, default=None)
    parser.add_argument("--openai-base-url", type=str,
                        default="https://api.openai.com/v1")
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--lang", choices=["en", "ko"], default="en")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--allow-partial", action="store_true")
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
        lang=args.lang,
        allow_partial=args.allow_partial,
    )

if __name__ == "__main__":
    main()
