"""Run reference-guided pairwise and single-answer grading."""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

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


def reference_single_input_fingerprint(
    question: MTBenchQuestion,
    answer: ModelAnswer,
    judge_model: str,
    lang: str,
    backend: Dict | None = None,
) -> str:
    return stable_fingerprint(
        {
            "protocol": "reference-single-fastchat-role-v3",
            "question_id": question.question_id,
            "category": question.category,
            "judge_model": judge_model,
            "backend": backend or {},
            "messages": build_multiturn_single_prompt(
                turns=question.turns,
                answers=answer.get_turns(),
                references=question.reference,
                lang=lang,
            ),
        }
    )

def reference_pairwise_input_fingerprint(
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
            "protocol": "reference-pairwise-ab-ba-fastchat-role-v3",
            "question_id": question.question_id,
            "category": question.category,
            "judge_model": judge_model,
            "backend": backend or {},
            "messages_ab": build_multiturn_pairwise_reference_prompt(
                turns=question.turns,
                answers_a=turns_a,
                answers_b=turns_b,
                references=question.reference or [],
                lang=lang,
            ),
            "messages_ba": build_multiturn_pairwise_reference_prompt(
                turns=question.turns,
                answers_a=turns_b,
                answers_b=turns_a,
                references=question.reference or [],
                lang=lang,
            ),
        }
    )

def reference_single_record_is_current(
    record: dict,
    question: MTBenchQuestion,
    model_id: str,
    judge_model: str,
    expected_hash: str,
) -> bool:
    """Reject malformed or mismatched reference-single records on resume."""
    score = record.get("score_turn2")
    valid_score = (
        isinstance(score, (int, float))
        and not isinstance(score, bool)
        and (score == -1 or 1 <= score <= 10)
    )
    return (
        record.get("question_id") == question.question_id
        and record.get("model_id") == model_id
        and record.get("judge_id") == judge_model
        and record.get("category") == question.category
        and record.get("input_sha256") == expected_hash
        and record.get("score_turn1") == -1
        and valid_score
        and record.get("judgment_turn1") == ""
        and isinstance(record.get("judgment_turn2"), str)
        and bool(record.get("judgment_turn2", "").strip())
    )

def reference_pairwise_record_is_current(
    record: dict,
    question: MTBenchQuestion,
    model_a_id: str,
    model_b_id: str,
    judge_model: str,
    expected_hash: str,
) -> bool:
    """Reject malformed or mismatched reference-pairwise records on resume."""
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

def grade_single_with_reference(
    question: MTBenchQuestion,
    answer: ModelAnswer,
    judge_client: ChatClient,
    judge_model: str = "gpt-4",
    lang: str = "en",
    reference_selection: str = "usable-turn2",
) -> Optional[JudgmentSingle]:
    """
    Reference answer가 있는 질문에 대해 reference-guided single grading 수행.

    Reference가 없는 경우 None 반환:
    - 모든 질문이 reference를 갖지는 않으므로 호출 측에서 필터링 가능.
    - reference 없는 질문은 judge_single.py에서 처리.

    Multi-turn single grading (reference-guided single-grade prompt):
    - 전체 대화 컨텍스트(q1, a1, q2, a2)와 reference(r1, r2)를
      하나의 프롬프트에 담아 2nd turn 답변을 채점.
    - turn1과 turn2를 합쳐 채점하는 방식 사용 (reference-guided single-grade prompt 기준).

    Args:
        question: reference 필드가 있는 MTBenchQuestion
        answer: 채점 대상 ModelAnswer
        judge_client: ChatClient 인스턴스
        judge_model: judge 모델명

    Returns:
        JudgmentSingle 또는 None (reference 없는 경우)
    """
    if reference_selection == "historical-declared":
        has_selected_reference = question.reference is not None
    elif reference_selection == "usable-turn2":
        has_selected_reference = question.has_reference_for_turn(1)
    else:
        raise ValueError(f"Unknown reference selection: {reference_selection}")
    if not has_selected_reference:
        logger.debug(
            "No selected reference for question_id=%s. Skipping.",
            question.question_id,
        )
        return None

    turns_q = question.turns
    turns_a = answer.get_turns()
    references = question.reference

    msgs = build_multiturn_single_prompt(
        turns=turns_q,
        answers=turns_a,
        references=references,
        lang=lang,
    )
    raw_judgment = judge_client.chat(
        messages=msgs,
        model=judge_model,
        temperature=0.0,
        max_tokens=1024,
    )

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
        score_turn1=-1.0,
        score_turn2=score,
        judgment_turn1="",
        judgment_turn2=raw_judgment,
        category=question.category,
        tstamp=time.time(),
        input_sha256=reference_single_input_fingerprint(
            question, answer, judge_model, lang, judge_client.fingerprint_identity()
        ),
    )

def judge_pairwise_with_reference(
    question: MTBenchQuestion,
    answer_a: ModelAnswer,
    answer_b: ModelAnswer,
    judge_client: ChatClient,
    judge_model: str = "gpt-4",
    lang: str = "en",
) -> Optional[JudgmentPairwise]:
    """
    Reference answer가 있는 질문에 대해 reference-guided pairwise 판정.

    reference-guided pairwise prompt(reference-guided) + multi-turn pairwise prompt(multi-turn)를 결합한 프롬프트 사용:
    - reference answer와 두 모델의 전체 2-turn 대화를 하나의 프롬프트에 담음.
    - judge가 reference를 기준으로 전체 대화 맥락에서 정확성을 비교.
    - 두 번째 턴에 사용할 수 있는 reference가 있는 문항만 대상으로 하며,
      첫 번째 턴의 reference가 비어 있으면 해당 블록은 생략함.

    position bias 완화를 위해 AB/BA swap을 수행하고, 두 판정이
    일치할 때만 winner를 선언한다.

    Args:
        question: reference 필드가 있는 MTBenchQuestion
        answer_a: 첫 번째 모델 답변
        answer_b: 두 번째 모델 답변
        judge_client: ChatClient 인스턴스
        judge_model: judge 모델명

    Returns:
        JudgmentPairwise 또는 None (reference 없는 경우)
    """
    if not question.has_reference_for_turn(1):
        logger.debug(f"No turn-two reference for question_id={question.question_id}.")
        return None

    turns_q = question.turns
    turns_a = answer_a.get_turns()
    turns_b = answer_b.get_turns()
    references = question.reference

    msgs_ab = build_multiturn_pairwise_reference_prompt(
        turns=turns_q,
        answers_a=turns_a,
        answers_b=turns_b,
        references=references,
        lang=lang,
    )
    raw_ab = judge_client.chat(
        messages=msgs_ab,
        model=judge_model,
        temperature=0.0,
        max_tokens=1024,
    )
    verdict_ab = parse_pairwise_verdict(raw_ab)

    msgs_ba = build_multiturn_pairwise_reference_prompt(
        turns=turns_q,
        answers_a=turns_b,
        answers_b=turns_a,
        references=references,
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
        input_sha256=reference_pairwise_input_fingerprint(
            question,
            answer_a,
            answer_b,
            judge_model,
            lang,
            judge_client.fingerprint_identity(),
        ),
    )

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
    lang: str = "en",
    allow_partial: bool = False,
    reference_selection: str = "usable-turn2",
) -> None:
    """
    Reference-guided single grading을 대상 카테고리 질문에 대해 수행.

    ``target_categories``의 기본값은
    ``REFERENCE_GUIDED_CATEGORIES``이다.

    출력 경로:
    - {output_dir}/single_grade_ref/{model_id}.jsonl
    - 일반 single grading 결과와 분리해 두 방식을 비교 분석할 수 있게 함.

    Args:
        target_categories: reference-guided를 적용할 카테고리 목록.
                           None이면 REFERENCE_GUIDED_CATEGORIES 사용.
        reference_selection: 선언 기준 29문항은
                             ``historical-declared``, 유효한 두 번째 턴
                             참조 26문항은 ``usable-turn2``.
    """
    if target_categories is None:
        target_categories = REFERENCE_GUIDED_CATEGORIES

    questions = load_questions(questions_path)
    if reference_selection == "historical-declared":
        ref_questions = [
            q for q in questions
            if q.reference is not None and q.category in target_categories
        ]
    elif reference_selection == "usable-turn2":
        ref_questions = [
            q for q in questions
            if q.has_reference_for_turn(1) and q.category in target_categories
        ]
    else:
        raise ValueError(f"Unknown reference selection: {reference_selection}")

    if not ref_questions:
        raise ValueError(
            f"No questions with reference found for categories: {target_categories}. "
            "FastChat mt_bench_questions.jsonl에 reference 필드가 있는지 확인하세요."
        )

    answers = load_answers(get_answer_path(answers_dir, model_id))

    safe_model = model_id.replace("/", "_")
    output_path = Path(output_dir) / "single_grade_ref" / f"{safe_model}.jsonl"

    if not resume and output_path.exists():
        output_path.unlink()
        logger.info(f"no-resume: removed existing {output_path}")

    expected_hashes = {
        question.question_id: reference_single_input_fingerprint(
            question,
            answers[question.question_id],
            judge_model,
            lang,
            judge_client.fingerprint_identity(),
        )
        for question in ref_questions
        if question.question_id in answers
    }
    existing_records = get_latest_records(output_path) if resume else {}
    current_records = {
        question.question_id: existing_records[question.question_id]
        for question in ref_questions
        if question.question_id in expected_hashes
        and question.question_id in existing_records
        and reference_single_record_is_current(
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
    missing = sorted(
        question.question_id
        for question in ref_questions
        if question.question_id not in answers
    )
    if missing:
        logger.warning("Missing answers for reference question_ids: %s", missing)
    pending = [
        question for question in ref_questions
        if question.question_id in answers
        and not reference_single_record_is_current(
            current_records.get(question.question_id, {}),
            question,
            model_id,
            judge_model,
            expected_hashes[question.question_id],
        )
    ]

    logger.info(
        f"Reference-guided single | model={model_id}, judge={judge_model}, "
        f"categories={target_categories}, pending={len(pending)}"
    )

    failed: List[int] = []
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
                lang=lang,
                reference_selection=reference_selection,
            )
            if judgment is not None:
                upsert_jsonl(output_path, judgment.to_dict())
        except Exception as e:
            failed.append(question.question_id)
            logger.error(
                f"Failed reference-guided grade for "
                f"question_id={question.question_id}: {e}"
            )

        if sleep_between_calls > 0:
            time.sleep(sleep_between_calls)

    final_records = get_latest_records(output_path)
    invalid = [
        question.question_id
        for question in ref_questions
        if question.question_id in answers
        and not reference_single_record_is_current(
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
        for question in ref_questions
        if question.question_id in expected_hashes
        and question.question_id in final_records
        and reference_single_record_is_current(
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
            "Reference-guided single grading incomplete; missing/failed "
            f"question_ids={incomplete}. Partial records were kept for resume."
        )
    logger.info(
        "Reference-guided single grading complete. Output: %s%s",
        output_path,
        f" (partial: {len(incomplete)} missing/failed)" if incomplete else "",
    )

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
    lang: str = "en",
    allow_partial: bool = False,
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
        if q.has_reference_for_turn(1) and q.category in target_categories
    ]

    if not ref_questions:
        raise ValueError("No reference questions found.")

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

    expected_hashes = {
        question.question_id: reference_pairwise_input_fingerprint(
            question,
            answers_a[question.question_id],
            answers_b[question.question_id],
            judge_model,
            lang,
            judge_client.fingerprint_identity(),
        )
        for question in ref_questions
        if question.question_id in answers_a and question.question_id in answers_b
    }
    existing_records = get_latest_records(output_path) if resume else {}
    current_records = {
        question.question_id: existing_records[question.question_id]
        for question in ref_questions
        if question.question_id in expected_hashes
        and question.question_id in existing_records
        and reference_pairwise_record_is_current(
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
        for question in ref_questions
        if question.question_id not in answers_a
        or question.question_id not in answers_b
    )
    if missing:
        logger.warning("Missing answers for reference question_ids: %s", missing)
    pending = [
        question for question in ref_questions
        if question.question_id in answers_a
        and question.question_id in answers_b
        and not reference_pairwise_record_is_current(
            current_records.get(question.question_id, {}),
            question,
            model_a_id,
            model_b_id,
            judge_model,
            expected_hashes[question.question_id],
        )
    ]

    logger.info(
        f"Reference-guided pairwise | {model_a_id} vs {model_b_id} | "
        f"judge={judge_model} | pending={len(pending)}"
    )

    failed: List[int] = []
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
                lang=lang,
            )
            if judgment is not None:
                upsert_jsonl(output_path, judgment.to_dict())
        except Exception as e:
            failed.append(question.question_id)
            logger.error(
                f"Failed reference pairwise for "
                f"question_id={question.question_id}: {e}"
            )

        if sleep_between_calls > 0:
            time.sleep(sleep_between_calls)

    final_records = get_latest_records(output_path)
    invalid = [
        question.question_id
        for question in ref_questions
        if question.question_id in answers_a
        and question.question_id in answers_b
        and not reference_pairwise_record_is_current(
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
        for question in ref_questions
        if question.question_id in expected_hashes
        and question.question_id in final_records
        and reference_pairwise_record_is_current(
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
            "Reference-guided pairwise grading incomplete; missing/failed "
            f"question_ids={incomplete}. Partial records were kept for resume."
        )
    logger.info(
        "Reference-guided pairwise complete. Output: %s%s",
        output_path,
        f" (partial: {len(incomplete)} missing/failed)" if incomplete else "",
    )

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MT-Bench Reference-guided Judge")
    parser.add_argument("--questions", type=str, default="data/en/questions.jsonl")
    parser.add_argument(
        "--answers-dir", type=str, default="runs/reproduction/en/answers/"
    )
    parser.add_argument(
        "--output-dir", type=str, default="runs/reproduction/en/judgments/"
    )
    parser.add_argument("--mode", type=str,
                        choices=["single", "pairwise"], default="single",
                        help="채점 모드: single (reference-guided single-grade prompt) 또는 pairwise (reference-guided pairwise prompt)")
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
    parser.add_argument("--lang", choices=["en", "ko"], default="en")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument(
        "--reference-selection",
        choices=["historical-declared", "usable-turn2"],
        default="usable-turn2",
    )
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
            lang=args.lang,
            allow_partial=args.allow_partial,
            reference_selection=args.reference_selection,
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
            lang=args.lang,
            allow_partial=args.allow_partial,
        )

if __name__ == "__main__":
    main()
