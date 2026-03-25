# src/mtbench_repro/generate.py
"""
MT-Bench 모델 답변 생성 (논문 Section 4.1).

왜 generate.py가 필요한가:
- 논문은 6개 오픈소스/클로즈드 모델의 MT-Bench 답변을 직접 생성해 저장한다.
- 각 질문에 대해 2-turn 대화를 수행한다:
    turn1: 1st 질문만 전달
    turn2: 이전 대화 컨텍스트 포함 (multi-turn)
- A100 서버에서 vLLM으로 실행하거나 --mock 플래그로 로컬 테스트 가능.

생성과 judge를 분리하는 이유:
- 생성은 GPU 서버(A100), judge는 GPT-4 API를 사용하므로 단계가 다르다.
- resume 지원: 이미 생성된 question_id는 재실행 시 skip.

논문 Temperature:
- 생성: 0.7 (Figure 3 주석 기준)
- Judge: 0.0 (deterministic)
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from typing import Dict, List

from mtbench_repro.client import ChatClient
from mtbench_repro.io_utils import (
    append_jsonl,
    get_answer_path,
    get_processed_ids,
    load_questions,
)
from mtbench_repro.schemas import ModelAnswer, MTBenchQuestion

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 단일 문항 답변 생성
# ---------------------------------------------------------------------------

def generate_answer(
    question: MTBenchQuestion,
    model_id: str,
    client: ChatClient,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> ModelAnswer:
    """
    하나의 질문에 대해 2-turn 대화를 생성한다.

    Turn 1:
        입력: [{"role": "user", "content": q1}]
        출력: a1

    Turn 2 (multi-turn — 논문 Section 2.2):
        입력: [{"role": "user",      "content": q1},
               {"role": "assistant", "content": a1},
               {"role": "user",      "content": q2}]
        출력: a2

    왜 turn2에 이전 context를 포함하는가:
    - MT-Bench 논문의 핵심 설계: 2nd turn은 1st turn 답변을 기반으로
      후속 질문에 답변하는 능력을 평가한다.
    - 이전 context 없이 독립적으로 2nd turn만 생성하면 논문 파이프라인과 다르다.

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

    # Turn 1
    msgs_t1 = [{"role": "user", "content": q1}]
    a1 = client.chat(msgs_t1, temperature=temperature, max_tokens=max_tokens)

    # Turn 2 — 이전 대화 컨텍스트 포함
    msgs_t2 = [
        {"role": "user",      "content": q1},
        {"role": "assistant", "content": a1},
        {"role": "user",      "content": q2},
    ]
    a2 = client.chat(msgs_t2, temperature=temperature, max_tokens=max_tokens)

    return ModelAnswer(
        question_id=question.question_id,
        model_id=model_id,
        choices=[{"index": 0, "turns": [a1, a2]}],
        tstamp=time.time(),
    )


# ---------------------------------------------------------------------------
# 전체 실행 함수
# ---------------------------------------------------------------------------

def run_generation(
    questions_path: str,
    answers_dir: str,
    model_id: str,
    client: ChatClient,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    sleep_between_calls: float = 1.0,
    resume: bool = True,
) -> None:
    """
    전체 MT-Bench 질문에 대해 모델 답변을 생성하고 JSONL로 저장.

    출력 경로 규칙:
    - {answers_dir}/{safe_model_id}.jsonl
    - model_id의 '/'는 '_'로 치환 (경로 안전성)

    Resume 동작:
    - resume=True이면 출력 파일에서 기존 question_id를 읽어 skip
    - API 실패 시 재실행해도 이미 생성된 결과 보존

    Args:
        questions_path: mt_bench_questions.jsonl 경로
        answers_dir: 답변 JSONL 저장 디렉토리
        model_id: 생성 모델 ID
        client: ChatClient 인스턴스
        temperature: 생성 temperature (기본 0.7)
        max_tokens: 최대 출력 토큰
        sleep_between_calls: API 호출 간 대기 (초)
        resume: True면 이미 처리된 question_id skip
    """
    questions = load_questions(questions_path)
    output_path = get_answer_path(answers_dir, model_id)

    # no-resume 시 기존 파일을 삭제해 append 누적 방지
    if not resume and output_path.exists():
        output_path.unlink()
        logger.info(f"no-resume: removed existing {output_path}")

    processed_ids = get_processed_ids(output_path) if resume else set()
    if processed_ids:
        logger.info(f"Resume: skipping {len(processed_ids)} already generated answers.")

    pending = [q for q in questions if q.question_id not in processed_ids]

    logger.info(
        f"Generation | model={model_id}, "
        f"total={len(questions)}, pending={len(pending)}"
    )

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
            )
            append_jsonl(output_path, answer.to_dict())
        except Exception as e:
            logger.error(
                f"Failed to generate answer for question_id={question.question_id}: {e}"
            )

        if sleep_between_calls > 0:
            time.sleep(sleep_between_calls)

    logger.info(f"Generation complete. Output: {output_path}")


# ---------------------------------------------------------------------------
# CLI 엔트리포인트 (python -m mtbench_repro.generate 직접 실행용)
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MT-Bench 모델 답변 생성")
    parser.add_argument("--questions", type=str,
                        default="data/mt_bench_questions.jsonl")
    parser.add_argument("--answers-dir", type=str, default="data/answers/")
    parser.add_argument("--model-id", type=str, required=True,
                        help="생성 모델 ID (vLLM served-model-name과 일치)")
    parser.add_argument("--vllm-host", type=str, default="localhost")
    parser.add_argument("--vllm-port", type=int, default=8000)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--mock", action="store_true",
                        help="mock client 사용 (API 없이 로컬 테스트)")
    parser.add_argument("--no-resume", action="store_true",
                        help="resume 비활성화 (처음부터 다시 실행)")
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
    )


if __name__ == "__main__":
    main()
