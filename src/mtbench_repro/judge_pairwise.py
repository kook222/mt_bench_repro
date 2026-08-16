"""Run AB/BA pairwise grading over complete two-turn conversations."""

from __future__ import annotations

import argparse
import itertools
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


def pairwise_input_fingerprint(
    question: MTBenchQuestion,
    answer_a: ModelAnswer,
    answer_b: ModelAnswer,
    judge_model: str,
    lang: str,
    backend: Dict | None = None,
) -> str:
    turns_a = answer_a.get_turns()
    turns_b = answer_b.get_turns()
    return stable_fingerprint(
        {
            "protocol": "pairwise-ab-ba-fastchat-role-v3",
            "question_id": question.question_id,
            "category": question.category,
            "judge_model": judge_model,
            "backend": backend or {},
            "messages_ab": build_multiturn_pairwise_prompt(
                turns=question.turns,
                answers_a=turns_a,
                answers_b=turns_b,
                lang=lang,
            ),
            "messages_ba": build_multiturn_pairwise_prompt(
                turns=question.turns,
                answers_a=turns_b,
                answers_b=turns_a,
                lang=lang,
            ),
        }
    )

def pairwise_record_is_current(
    record: dict,
    question: MTBenchQuestion,
    model_a_id: str,
    model_b_id: str,
    judge_model: str,
    expected_hash: str,
) -> bool:
    """Reject malformed or mismatched pairwise records during resume."""
    winner_ab = record.get("winner_ab")
    winner_ba = record.get("winner_ba")
    resolved_winner = (
        resolve_pairwise_winner(winner_ab, winner_ba, model_a_id, model_b_id)
        if winner_ab in {"A", "B", "tie", "error"}
        and winner_ba in {"A", "B", "tie", "error"}
        else None
    )
    return (
        record.get("question_id") == question.question_id
        and record.get("model_a") == model_a_id
        and record.get("model_b") == model_b_id
        and record.get("judge_id") == judge_model
        and record.get("category") == question.category
        and record.get("turn") == 2
        and record.get("input_sha256") == expected_hash
        and record.get("winner") == resolved_winner
        and isinstance(record.get("judgment_ab"), str)
        and bool(record.get("judgment_ab", "").strip())
        and isinstance(record.get("judgment_ba"), str)
        and bool(record.get("judgment_ba", "").strip())
    )

def judge_pairwise_question(
    question: MTBenchQuestion,
    answer_a: ModelAnswer,
    answer_b: ModelAnswer,
    judge_client: ChatClient,
    judge_model: str = "gpt-4",
    lang: str = "en",
) -> JudgmentPairwise:
    """
    한 질문에 대해 두 모델의 답변을 비교 판정. AB/BA 순서로 각 1회 호출.

    2-turn 전체 대화를 하나의 multi-turn 프롬프트에 담는다.

    Conservative verdict 결정:
    - AB 판정과 BA 판정이 일치 → 해당 모델 ID를 winner로 기록
    - 불일치 → "inconsistent" (공식 승률에서 tie, 조건부 승률에서 제외)

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

    msgs_ab = build_multiturn_pairwise_prompt(
        turns=turns_q,
        answers_a=turns_a,
        answers_b=turns_b,
        lang=lang,
    )
    raw_ab = judge_client.chat(
        messages=msgs_ab,
        model=judge_model,
        temperature=0.0,
        max_tokens=1024,
    )
    verdict_ab = parse_pairwise_verdict(raw_ab)

    msgs_ba = build_multiturn_pairwise_prompt(
        turns=turns_q,
        answers_a=turns_b,
        answers_b=turns_a,
        lang=lang,
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
        turn=2,
        category=question.category,
        tstamp=time.time(),
        input_sha256=pairwise_input_fingerprint(
            question,
            answer_a,
            answer_b,
            judge_model,
            lang,
            judge_client.fingerprint_identity(),
        ),
    )

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
    lang: str = "en",
    allow_partial: bool = False,
) -> None:
    """
    두 모델 간 pairwise comparison을 전체 MT-Bench 질문에 대해 수행.

    출력 경로 규칙:
    - {output_dir}/pairwise/{model_a}_vs_{model_b}.jsonl
    - 파일명이 길어지는 문제를 방지하기 위해 '/'는 '_'로 치환.

    재실행 안전성:
    - 질문·두 답안·judge prompt fingerprint가 같은 레코드만 재사용.
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
        resume: True면 입력 fingerprint가 같은 문항만 건너뜀
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

    expected_hashes = {
        question.question_id: pairwise_input_fingerprint(
            question,
            answers_a[question.question_id],
            answers_b[question.question_id],
            judge_model,
            lang,
            judge_client.fingerprint_identity(),
        )
        for question in questions
        if question.question_id in answers_a and question.question_id in answers_b
    }
    existing_records = get_latest_records(output_path) if resume else {}
    current_records = {
        question.question_id: existing_records[question.question_id]
        for question in questions
        if question.question_id in expected_hashes
        and question.question_id in existing_records
        and pairwise_record_is_current(
            existing_records[question.question_id],
            question,
            model_a_id,
            model_b_id,
            judge_model,
            expected_hashes[question.question_id],
        )
    }
    if existing_records != current_records:
        write_jsonl_atomic(
            output_path,
            [current_records[qid] for qid in sorted(current_records)],
        )

    missing = sorted(
        question.question_id
        for question in questions
        if question.question_id not in answers_a
        or question.question_id not in answers_b
    )
    if missing:
        logger.warning("Missing answers for question_ids: %s", missing)

    pending = [
        question for question in questions
        if question.question_id in answers_a
        and question.question_id in answers_b
        and not pairwise_record_is_current(
            current_records.get(question.question_id, {}),
            question,
            model_a_id,
            model_b_id,
            judge_model,
            expected_hashes[question.question_id],
        )
    ]

    logger.info(
        f"Pairwise | {model_a_id} vs {model_b_id} | "
        f"judge={judge_model} | pending={len(pending)}"
    )

    failed: List[int] = []
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
                lang=lang,
            )
            upsert_jsonl(output_path, judgment.to_dict())
        except Exception as e:
            failed.append(question.question_id)
            logger.error(
                f"Failed pairwise for question_id={question.question_id}: {e}"
            )

        if sleep_between_calls > 0:
            time.sleep(sleep_between_calls)

    final_records = get_latest_records(output_path)
    invalid = [
        question.question_id
        for question in questions
        if question.question_id in answers_a
        and question.question_id in answers_b
        and not pairwise_record_is_current(
            final_records.get(question.question_id, {}),
            question,
            model_a_id,
            model_b_id,
            judge_model,
            expected_hashes[question.question_id],
        )
    ]
    incomplete = sorted(set(missing + failed + invalid))
    valid_final_records = {
        question.question_id: final_records[question.question_id]
        for question in questions
        if question.question_id in expected_hashes
        and question.question_id in final_records
        and pairwise_record_is_current(
            final_records[question.question_id],
            question,
            model_a_id,
            model_b_id,
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
            "Pairwise grading incomplete; missing/failed question_ids="
            f"{incomplete}. Partial records were kept for hash-aware resume."
        )
    logger.info(
        "Pairwise complete. Output: %s%s",
        output_path,
        f" (partial: {len(incomplete)} missing/failed)" if incomplete else "",
    )

def run_all_pairs(
    questions_path: str,
    answers_dir: str,
    output_dir: str,
    model_ids: List[str],
    judge_client: ChatClient,
    judge_model: str = "gpt-4",
    sleep_between_calls: float = 2.0,
    resume: bool = True,
    lang: str = "en",
    allow_partial: bool = False,
) -> None:
    """
    모델 목록에서 가능한 모든 pairs에 대해 pairwise comparison 실행.

    ``combinations(model_ids, 2)``로 중복 없이 순서 없는 쌍을 생성.

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
            lang=lang,
            allow_partial=allow_partial,
        )

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MT-Bench Pairwise Judge")
    parser.add_argument("--questions", type=str, default="data/en/questions.jsonl")
    parser.add_argument(
        "--answers-dir", type=str, default="runs/reproduction/en/answers/"
    )
    parser.add_argument(
        "--output-dir", type=str, default="runs/reproduction/en/judgments/"
    )
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
            lang=args.lang,
            allow_partial=args.allow_partial,
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
            lang=args.lang,
            allow_partial=args.allow_partial,
        )
    else:
        raise ValueError("--model-a/--model-b 또는 --models 중 하나를 지정해야 합니다.")

if __name__ == "__main__":
    main()
