"""Generate two-turn MT-Bench answers with hash-aware resume."""

from __future__ import annotations

import argparse
import logging
import time
from typing import Dict, List

from mtbench_repro.client import ChatClient
from mtbench_repro.io_utils import (
    get_answer_path,
    get_latest_records,
    load_questions,
    stable_fingerprint,
    upsert_jsonl,
    write_jsonl_atomic,
)
from mtbench_repro.schemas import ModelAnswer, MTBenchQuestion

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def generation_input_fingerprint(
    question: MTBenchQuestion,
    model_id: str,
    temperature: float,
    max_tokens: int,
    system_prompt: str | None,
    backend: Dict | None = None,
) -> str:
    return stable_fingerprint(
        {
            "protocol": "generation-v2",
            "question": {
                "question_id": question.question_id,
                "category": question.category,
                "turns": question.turns,
            },
            "model_id": model_id,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "system_prompt": system_prompt,
            "backend": backend or {},
        }
    )

def answer_record_is_current(
    record: dict,
    question_id: int,
    model_id: str,
    expected_hash: str,
) -> bool:
    """Reject truncated or mismatched answer records during resume."""
    choices = record.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        return False
    choice = choices[0]
    if not isinstance(choice, dict) or choice.get("index") != 0:
        return False
    turns = choice.get("turns")
    return (
        record.get("question_id") == question_id
        and record.get("model_id") == model_id
        and record.get("input_sha256") == expected_hash
        and isinstance(turns, list)
        and len(turns) == 2
        and all(isinstance(turn, str) and turn.strip() for turn in turns)
    )

def generate_answer(
    question: MTBenchQuestion,
    model_id: str,
    client: ChatClient,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    system_prompt: str | None = None,
) -> ModelAnswer:
    """
    하나의 질문에 대해 2-turn 대화를 생성한다.

    Turn 1:
        입력: [{"role": "user", "content": q1}]
        출력: a1

    Turn 2 (multi-turn):
        입력: [{"role": "user",      "content": q1},
               {"role": "assistant", "content": a1},
               {"role": "user",      "content": q2}]
        출력: a2

    두 번째 턴은 MT-Bench 대화 구조를 유지하도록 이전 질문과
    답변을 포함한다.

    Args:
        question: MTBenchQuestion 인스턴스
        model_id: 생성 모델 식별자 (ModelAnswer에 저장)
        client: ChatClient (vLLM 또는 mock)
        temperature: 생성 다양성 (기본 0.7)
        max_tokens: 최대 출력 토큰 수

    Returns:
        ModelAnswer 인스턴스
    """
    q1 = question.turns[0]
    q2 = question.turns[1]

    q1_input = f"{system_prompt}\n\n{q1}" if system_prompt else q1

    msgs_t1 = [{"role": "user", "content": q1_input}]
    a1 = client.chat(
        msgs_t1,
        model=model_id,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    msgs_t2 = [
        {"role": "user",      "content": q1_input},
        {"role": "assistant", "content": a1},
        {"role": "user",      "content": q2},
    ]
    a2 = client.chat(
        msgs_t2,
        model=model_id,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    return ModelAnswer(
        question_id=question.question_id,
        model_id=model_id,
        choices=[{"index": 0, "turns": [a1, a2]}],
        tstamp=time.time(),
        input_sha256=generation_input_fingerprint(
            question,
            model_id,
            temperature,
            max_tokens,
            system_prompt,
            client.fingerprint_identity(),
        ),
    )

def run_generation(
    questions_path: str,
    answers_dir: str,
    model_id: str,
    client: ChatClient,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    sleep_between_calls: float = 1.0,
    resume: bool = True,
    system_prompt: str | None = None,
    allow_partial: bool = False,
) -> None:
    """
    전체 MT-Bench 질문에 대해 모델 답변을 생성하고 JSONL로 저장.

    출력 경로 규칙:
    - {answers_dir}/{safe_model_id}.jsonl
    - model_id의 '/'는 '_'로 치환 (경로 안전성)

    Resume 동작:
    - resume=True이면 입력 fingerprint가 같은 기존 레코드만 건너뜀
    - API 실패 시 재실행해도 이미 생성된 결과 보존

    Args:
        questions_path: mt_bench_questions.jsonl 경로
        answers_dir: 답변 JSONL 저장 디렉토리
        model_id: 생성 모델 ID
        client: ChatClient 인스턴스
        temperature: 생성 temperature (기본 0.7)
        max_tokens: 최대 출력 토큰
        sleep_between_calls: API 호출 간 대기 (초)
        resume: True면 입력 fingerprint가 같은 문항만 건너뜀
    """
    questions = load_questions(questions_path)
    output_path = get_answer_path(answers_dir, model_id)

    if not resume and output_path.exists():
        output_path.unlink()
        logger.info(f"no-resume: removed existing {output_path}")

    expected_hashes = {
        question.question_id: generation_input_fingerprint(
            question,
            model_id,
            temperature,
            max_tokens,
            system_prompt,
            client.fingerprint_identity(),
        )
        for question in questions
    }
    existing_records = get_latest_records(output_path) if resume else {}
    current_records = {
        question.question_id: existing_records[question.question_id]
        for question in questions
        if question.question_id in existing_records
        and answer_record_is_current(
            existing_records[question.question_id],
            question.question_id,
            model_id,
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
        if not answer_record_is_current(
            current_records.get(question.question_id, {}),
            question.question_id,
            model_id,
            expected_hashes[question.question_id],
        )
    ]
    if existing_records:
        logger.info(
            "Hash-aware resume: %d up-to-date, %d stale or missing",
            len(questions) - len(pending),
            len(pending),
        )

    logger.info(
        f"Generation | model={model_id}, "
        f"total={len(questions)}, pending={len(pending)}"
    )

    failed: List[int] = []
    for i, question in enumerate(pending, start=1):
        logger.info(
            f"[{i}/{len(pending)}] Generating question_id={question.question_id}, "
            f"category={question.category}"
        )
        try:
            answer = generate_answer(
                question=question,
                model_id=model_id,
                client=client,
                temperature=temperature,
                max_tokens=max_tokens,
                system_prompt=system_prompt,
            )
            upsert_jsonl(output_path, answer.to_dict())
        except Exception as e:
            failed.append(question.question_id)
            logger.error(
                f"Failed to generate answer for question_id={question.question_id}: {e}"
            )

        if sleep_between_calls > 0:
            time.sleep(sleep_between_calls)

    final_records = get_latest_records(output_path)
    invalid = [
        question.question_id
        for question in questions
        if not answer_record_is_current(
            final_records.get(question.question_id, {}),
            question.question_id,
            model_id,
            expected_hashes[question.question_id],
        )
    ]
    incomplete = sorted(set(failed + invalid))
    valid_final_records = {
        question.question_id: final_records[question.question_id]
        for question in questions
        if question.question_id in final_records
        and answer_record_is_current(
            final_records[question.question_id],
            question.question_id,
            model_id,
            expected_hashes[question.question_id],
        )
    }
    write_jsonl_atomic(
        output_path,
        [valid_final_records[qid] for qid in sorted(valid_final_records)],
    )
    if incomplete and not allow_partial:
        raise RuntimeError(
            "Generation incomplete; failed/invalid question_ids="
            f"{incomplete}. Partial records were kept for hash-aware resume."
        )
    logger.info(
        "Generation complete. Output: %s%s",
        output_path,
        f" (partial: {len(incomplete)} failed/invalid)" if incomplete else "",
    )

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MT-Bench 모델 답변 생성")
    parser.add_argument("--questions", type=str,
                        default="data/en/questions.jsonl")
    parser.add_argument(
        "--answers-dir", type=str, default="runs/reproduction/en/answers/"
    )
    parser.add_argument("--model-id", type=str, required=True,
                        help="생성 모델 ID (vLLM served-model-name과 일치)")
    parser.add_argument("--vllm-host", type=str, default="localhost")
    parser.add_argument("--vllm-port", type=int, default=8000)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--system-prompt", type=str, default=None,
                        help="시스템 프롬프트 (한국어 생성 시: '반드시 한국어로 답하세요.'")
    parser.add_argument("--mock", action="store_true",
                        help="mock client 사용 (API 없이 로컬 테스트)")
    parser.add_argument("--no-resume", action="store_true",
                        help="resume 비활성화 (처음부터 다시 실행)")
    parser.add_argument("--allow-partial", action="store_true")
    return parser.parse_args()

def main() -> None:
    args = parse_args()

    if args.mock:
        client = ChatClient.mock()
    else:
        client = ChatClient.from_vllm(
            host=args.vllm_host,
            port=args.vllm_port,
            model=args.model_id,
        )

    run_generation(
        questions_path=args.questions,
        answers_dir=args.answers_dir,
        model_id=args.model_id,
        client=client,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        sleep_between_calls=args.sleep,
        resume=not args.no_resume,
        system_prompt=args.system_prompt,
        allow_partial=args.allow_partial,
    )

if __name__ == "__main__":
    main()
