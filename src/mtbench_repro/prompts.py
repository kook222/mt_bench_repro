# src/prompts.py
"""
논문 Appendix A (Figure 5~10)의 프롬프트 템플릿과 파싱 함수 모음.

왜 prompts.py에 파싱까지 포함하는가:
- 프롬프트 형식과 파싱 패턴은 강하게 결합되어 있다.
  예: "[[A]]"/"[[B]]"/"[[C]]" 형식은 Figure 5/8/9 프롬프트가 요구하는 형식이고,
  "Rating: [[5]]" 형식은 Figure 6/10 프롬프트가 요구한다.
  두 관심사를 분리하면 포맷이 바뀔 때 파일을 두 곳 수정해야 한다.
- judge_single.py, judge_pairwise.py, judge_reference.py는
  이 파일에서 build_ 함수와 parse_ 함수만 가져다 쓴다.

프롬프트 원칙:
- 논문 원문(Figure 5~10)을 최대한 그대로 유지한다.
- 변수 자리는 Python str.format() 스타일 대신 명시적 파라미터로 처리해
  빠진 값이 있으면 TypeError로 즉시 알 수 있게 한다.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple


# ===========================================================================
# 시스템 프롬프트 상수 (논문 Appendix A 원문)
# ===========================================================================

# Figure 5: default prompt for pairwise comparison
# 논문 원문 그대로 유지 — 수정 시 논문 근거 명시 필요
_SYSTEM_PAIRWISE = (
    "Please act as an impartial judge and evaluate the quality of the responses "
    "provided by two AI assistants to the user question displayed below. "
    "You should choose the assistant that follows the user's instructions and "
    "answers the user's question better. Your evaluation should consider factors "
    "such as the helpfulness, relevance, accuracy, depth, creativity, and level "
    "of detail of their responses. Begin your evaluation by comparing the two "
    "responses and provide a short explanation. Avoid any position biases and "
    "ensure that the order in which the responses were presented does not "
    "influence your decision. Do not allow the length of the responses to "
    "influence your evaluation. Do not favor certain names of the assistants. "
    "Be as objective as possible. After providing your explanation, output your "
    "final verdict by strictly following this format: \"[[A]]\" if assistant A "
    "is better, \"[[B]]\" if assistant B is better, and \"[[C]]\" for a tie."
)

# Figure 6: default prompt for single answer grading
_SYSTEM_SINGLE = (
    "Please act as an impartial judge and evaluate the quality of the response "
    "provided by an AI assistant to the user question displayed below. Your "
    "evaluation should consider factors such as the helpfulness, relevance, "
    "accuracy, depth, creativity, and level of detail of the response. Begin "
    "your evaluation by providing a short explanation. Be as objective as "
    "possible. After providing your explanation, please rate the response on a "
    "scale of 1 to 10 by strictly following this format: \"[[rating]]\", for "
    "example: \"Rating: [[5]]\"."
)

# Figure 7: chain-of-thought prompt for math/reasoning pairwise
# 논문 Section 3.4: CoT judge는 먼저 독립적으로 풀고 나서 채점
_SYSTEM_PAIRWISE_MATH_COT = (
    "Please act as an impartial judge and evaluate the quality of the responses "
    "provided by two AI assistants to the user question displayed below. Your "
    "evaluation should consider correctness and helpfulness. You will be given "
    "assistant A's answer, and assistant B's answer. Your job is to evaluate "
    "which assistant's answer is better. You should independently solve the user "
    "question step-by-step first. Then compare both assistants' answers with "
    "your answer. Identify and correct any mistakes. Avoid any position biases "
    "and ensure that the order in which the responses were presented does not "
    "influence your decision. Do not allow the length of the responses to "
    "influence your evaluation. Do not favor certain names of the assistants. "
    "Be as objective as possible. After providing your explanation, output your "
    "final verdict by strictly following this format: \"[[A]]\" if assistant A "
    "is better, \"[[B]]\" if assistant B is better, and \"[[C]]\" for a tie."
)

# Figure 8: reference-guided pairwise comparison
# 논문 Section 3.4, Table 4: reference 제공 시 failure rate 70%→15%
_SYSTEM_PAIRWISE_REFERENCE = (
    "Please act as an impartial judge and evaluate the quality of the responses "
    "provided by two AI assistants to the user question displayed below. Your "
    "evaluation should consider correctness and helpfulness. You will be given a "
    "reference answer, assistant A's answer, and assistant B's answer. Your job "
    "is to evaluate which assistant's answer is better. Begin your evaluation by "
    "comparing both assistants' answers with the reference answer. Identify and "
    "correct any mistakes. Avoid any position biases and ensure that the order "
    "in which the responses were presented does not influence your decision. Do "
    "not allow the length of the responses to influence your evaluation. Do not "
    "favor certain names of the assistants. Be as objective as possible. After "
    "providing your explanation, output your final verdict by strictly following "
    "this format: \"[[A]]\" if assistant A is better, \"[[B]]\" if assistant B "
    "is better, and \"[[C]]\" for a tie."
)

# Figure 10: reference-guided multi-turn single-answer grading
_SYSTEM_SINGLE_REFERENCE = (
    "Please act as an impartial judge and evaluate the quality of the response "
    "provided by an AI assistant to the user question. Your evaluation should "
    "consider correctness and helpfulness. You will be given a reference answer "
    "and the assistant's answer. Your evaluation should focus on the assistant's "
    "answer to the second question. Begin your evaluation by comparing the "
    "assistant's answer with the reference answer. Identify and correct any "
    "mistakes. Be as objective as possible. After providing your explanation, "
    "you must rate the response on a scale of 1 to 10 by strictly following "
    "this format: \"[[rating]]\", for example: \"Rating: [[5]]\"."
)


# ===========================================================================
# Pairwise 프롬프트 빌더 (Figure 5, 7, 8, 9)
# ===========================================================================

def build_pairwise_prompt(
    question: str,
    answer_a: str,
    answer_b: str,
    reference: Optional[str] = None,
    use_cot: bool = False,
) -> List[Dict[str, str]]:
    """
    Single-turn pairwise 비교 프롬프트 생성 (Figure 5 / 7 / 8).

    reference가 있으면 Figure 8, use_cot이면 Figure 7,
    둘 다 없으면 Figure 5를 사용한다.
    논문 Section 3.4: reference가 CoT보다 효과적 (Table 4 근거).

    Args:
        question: 1st turn 질문 텍스트
        answer_a: Assistant A의 답변
        answer_b: Assistant B의 답변
        reference: 참조 답변 (math/coding 전용, Figure 8)
        use_cot: True면 Figure 7 CoT 프롬프트 사용

    Returns:
        [{"role": "system", "content": ...}, {"role": "user", "content": ...}]
        형식의 messages 리스트 (ChatClient.chat()에 직접 전달 가능)
    """
    if reference is not None:
        system = _SYSTEM_PAIRWISE_REFERENCE
        user_content = (
            f"[User Question]\n{question}\n\n"
            f"[The Start of Reference Answer]\n{reference}\n"
            f"[The End of Reference Answer]\n\n"
            f"[The Start of Assistant A's Answer]\n{answer_a}\n"
            f"[The End of Assistant A's Answer]\n\n"
            f"[The Start of Assistant B's Answer]\n{answer_b}\n"
            f"[The End of Assistant B's Answer]"
        )
    elif use_cot:
        system = _SYSTEM_PAIRWISE_MATH_COT
        user_content = (
            f"[User Question]\n{question}\n\n"
            f"[The Start of Assistant A's Answer]\n{answer_a}\n"
            f"[The End of Assistant A's Answer]\n\n"
            f"[The Start of Assistant B's Answer]\n{answer_b}\n"
            f"[The End of Assistant B's Answer]"
        )
    else:
        system = _SYSTEM_PAIRWISE
        user_content = (
            f"[User Question]\n{question}\n\n"
            f"[The Start of Assistant A's Answer]\n{answer_a}\n"
            f"[The End of Assistant A's Answer]\n\n"
            f"[The Start of Assistant B's Answer]\n{answer_b}\n"
            f"[The End of Assistant B's Answer]"
        )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]


def build_multiturn_pairwise_prompt(
    turns: List[str],
    answers_a: List[str],
    answers_b: List[str],
) -> List[Dict[str, str]]:
    """
    Multi-turn pairwise 비교 프롬프트 생성 (Figure 9).

    논문 Section 3.5:
    - 두 대화 전체를 하나의 프롬프트에 담아 judge에게 2nd turn 집중 요청.
    - 두 turn을 별도 프롬프트로 분리하면 judge가 이전 답변을 잘못 참조함.

    Args:
        turns: [1st_turn_question, 2nd_turn_question]
        answers_a: [1st_answer_A, 2nd_answer_A]
        answers_b: [1st_answer_B, 2nd_answer_B]

    Returns:
        messages 리스트
    """
    assert len(turns) == 2, "MT-Bench는 정확히 2-turn 질문이어야 합니다."
    assert len(answers_a) == 2 and len(answers_b) == 2

    conv_a = (
        f"<|The Start of Assistant A's Conversation with User|>\n"
        f"### User:\n{turns[0]}\n"
        f"### Assistant A:\n{answers_a[0]}\n"
        f"### User:\n{turns[1]}\n"
        f"### Assistant A:\n{answers_a[1]}\n"
        f"<|The End of Assistant A's Conversation with User|>"
    )
    conv_b = (
        f"<|The Start of Assistant B's Conversation with User|>\n"
        f"### User:\n{turns[0]}\n"
        f"### Assistant B:\n{answers_b[0]}\n"
        f"### User:\n{turns[1]}\n"
        f"### Assistant B:\n{answers_b[1]}\n"
        f"<|The End of Assistant B's Conversation with User|>"
    )

    return [
        {"role": "system", "content": _SYSTEM_PAIRWISE},
        {"role": "user", "content": f"{conv_a}\n\n{conv_b}"},
    ]


# ===========================================================================
# Reference-guided multi-turn pairwise (Figure 8 × Figure 9 결합)
# ===========================================================================

def build_multiturn_pairwise_reference_prompt(
    turns: List[str],
    answers_a: List[str],
    answers_b: List[str],
    references: List[str],
) -> List[Dict[str, str]]:
    """
    Multi-turn reference-guided pairwise 프롬프트 (Figure 8 + Figure 9 결합).

    Figure 8(reference-guided)과 Figure 9(multi-turn)를 결합:
    - reference answer(1st/2nd turn 모두)를 judge에게 제공
    - 두 모델의 전체 2-turn 대화를 하나의 프롬프트에 담음
    - judge가 reference 기준으로 두 모델의 정확성을 전체 대화 맥락에서 비교

    기존 단순화 방식(1st turn만, single-turn 포맷) 대비 차이:
    - 2nd turn 답변까지 함께 제공해 judge가 대화 전체를 평가
    - 2nd turn reference가 있으면 함께 제공 (없어도 동작)

    Args:
        turns: [1st_turn_question, 2nd_turn_question]
        answers_a: [1st_answer_A, 2nd_answer_A]
        answers_b: [1st_answer_B, 2nd_answer_B]
        references: [1st_reference] 또는 [1st_reference, 2nd_reference]

    Returns:
        messages 리스트
    """
    assert len(turns) == 2 and len(answers_a) == 2 and len(answers_b) == 2
    assert len(references) >= 1, "reference가 최소 1개 필요합니다."

    # Reference block — Figure 10의 표현 방식 준용, 2nd turn reference는 선택적
    ref_turn1 = (
        f"### User:\n{turns[0]}\n"
        f"### Reference answer:\n{references[0]}"
    )
    ref_turn2 = (
        f"### User:\n{turns[1]}\n"
        f"### Reference answer:\n{references[1]}"
        if len(references) >= 2
        else f"### User:\n{turns[1]}"
    )
    ref_block = (
        f"<|The Start of Reference Answer|>\n"
        f"{ref_turn1}\n"
        f"{ref_turn2}\n"
        f"<|The End of Reference Answer|>"
    )

    # 두 모델의 전체 대화 — Figure 9 방식
    conv_a = (
        f"<|The Start of Assistant A's Conversation with User|>\n"
        f"### User:\n{turns[0]}\n"
        f"### Assistant A:\n{answers_a[0]}\n"
        f"### User:\n{turns[1]}\n"
        f"### Assistant A:\n{answers_a[1]}\n"
        f"<|The End of Assistant A's Conversation with User|>"
    )
    conv_b = (
        f"<|The Start of Assistant B's Conversation with User|>\n"
        f"### User:\n{turns[0]}\n"
        f"### Assistant B:\n{answers_b[0]}\n"
        f"### User:\n{turns[1]}\n"
        f"### Assistant B:\n{answers_b[1]}\n"
        f"<|The End of Assistant B's Conversation with User|>"
    )

    return [
        {"role": "system", "content": _SYSTEM_PAIRWISE_REFERENCE},
        {"role": "user", "content": f"{ref_block}\n\n{conv_a}\n\n{conv_b}"},
    ]


# ===========================================================================
# Single-answer grading 프롬프트 빌더 (Figure 6, 10)
# ===========================================================================

def build_single_prompt(
    question: str,
    answer: str,
    reference: Optional[str] = None,
) -> List[Dict[str, str]]:
    """
    Single-answer grading 프롬프트 생성 (Figure 6).

    논문 Table 8: GPT-4 single-answer grading으로 MT-Bench Score 산출.
    각 turn마다 별도 호출하고, 두 점수를 평균내어 최종 점수를 낸다.

    Args:
        question: 해당 turn의 질문
        answer: 채점할 답변
        reference: 참조 답변 (있으면 Figure 6가 아닌 변형 사용)

    Returns:
        messages 리스트
    """
    if reference is not None:
        # reference가 있으면 system 프롬프트를 correctness 중심으로 변경
        system = _SYSTEM_SINGLE_REFERENCE
        user_content = (
            f"[Question]\n{question}\n\n"
            f"[Reference Answer]\n{reference}\n\n"
            f"[The Start of Assistant's Answer]\n{answer}\n"
            f"[The End of Assistant's Answer]"
        )
    else:
        system = _SYSTEM_SINGLE
        user_content = (
            f"[Question]\n{question}\n\n"
            f"[The Start of Assistant's Answer]\n{answer}\n"
            f"[The End of Assistant's Answer]"
        )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]


def build_multiturn_single_prompt(
    turns: List[str],
    answers: List[str],
    references: Optional[List[str]] = None,
) -> List[Dict[str, str]]:
    """
    Multi-turn single-answer grading 프롬프트 생성 (Figure 10).

    논문 Section 3.5, Figure 10:
    - reference answer가 있을 때 전체 대화 맥락을 포함해 2nd turn 채점.
    - 주로 math/coding 카테고리에서 reference와 함께 사용.

    Args:
        turns: [1st_turn_question, 2nd_turn_question]
        answers: [1st_answer, 2nd_answer]
        references: [1st_ref, 2nd_ref] (선택적)

    Returns:
        messages 리스트
    """
    assert len(turns) == 2 and len(answers) == 2

    if references is not None:
        # turn1 reference는 항상 존재, turn2 reference는 없을 수도 있음
        ref_turn1 = (
            f"### User:\n{turns[0]}\n"
            f"### Reference answer:\n{references[0]}"
        )
        ref_turn2 = (
            f"### User:\n{turns[1]}\n"
            f"### Reference answer:\n{references[1]}"
            if len(references) >= 2
            else f"### User:\n{turns[1]}"
        )
        ref_block = (
            f"<|The Start of Reference Answer|>\n"
            f"{ref_turn1}\n"
            f"{ref_turn2}\n"
            f"<|The End of Reference Answer|>\n\n"
        )
        system = _SYSTEM_SINGLE_REFERENCE
    else:
        ref_block = ""
        system = _SYSTEM_SINGLE

    conv = (
        f"<|The Start of Assistant A's Conversation with User|>\n"
        f"### User:\n{turns[0]}\n"
        f"### Assistant A:\n{answers[0]}\n"
        f"### User:\n{turns[1]}\n"
        f"### Assistant A:\n{answers[1]}\n"
        f"<|The End of Assistant A's Conversation with User|>"
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"{ref_block}{conv}"},
    ]


# ===========================================================================
# 파싱 함수
# ===========================================================================

def parse_pairwise_verdict(text: str) -> str:
    """
    Pairwise judge 응답에서 최종 판정을 파싱.

    논문 Figure 5/7/8/9의 출력 형식:
    - "[[A]]": Assistant A가 더 좋음
    - "[[B]]": Assistant B가 더 좋음
    - "[[C]]": 동점 (tie)

    파싱 전략:
    - 마지막으로 등장하는 [[X]]를 결과로 사용.
      judge가 설명 중에 [[A]]를 언급하고 결론에서 [[B]]를 쓰는 경우를 처리.
    - 파싱 실패 시 "error" 반환 (빈 문자열이나 예외 대신).
      aggregate.py에서 error 비율을 별도 추적하기 위함.

    Args:
        text: judge LLM의 원문 응답

    Returns:
        "A" | "B" | "tie" | "error"
    """
    if not text:
        return "error"

    # 마지막 [[X]] 패턴 찾기
    matches = re.findall(r"\[\[([ABCabc])\]\]", text)
    if not matches:
        return "error"

    verdict = matches[-1].upper()
    if verdict == "C":
        return "tie"
    return verdict  # "A" 또는 "B"


def parse_single_score(text: str) -> float:
    """
    Single-answer grading 응답에서 점수를 파싱.

    논문 Figure 6의 출력 형식: "Rating: [[5]]"
    점수 범위: 1~10 (정수 또는 소수)

    파싱 전략:
    - "[[숫자]]" 패턴의 마지막 매치를 사용.
    - 범위(1~10) 벗어나면 -1 반환.
    - 파싱 실패 시 -1 반환 (NaN 대신 -1을 쓰는 이유:
      JudgmentSingle.avg_score에서 -1을 명시적으로 체크해
      집계에서 제외하기 위함).

    Args:
        text: judge LLM의 원문 응답

    Returns:
        1.0~10.0 사이의 점수, 파싱 실패 시 -1.0
    """
    if not text:
        return -1.0

    # "[[숫자]]" 패턴: 정수 및 소수 모두 허용
    matches = re.findall(r"\[\[(\d+(?:\.\d+)?)\]\]", text)
    if not matches:
        # fallback: "Rating: 9" 또는 "Rating: [[9]]" 없이 숫자만 있는 경우
        matches = re.findall(r"[Rr]ating:\s*(\d+(?:\.\d+)?)", text)
    if not matches:
        return -1.0

    try:
        score = float(matches[-1])
        if 1.0 <= score <= 10.0:
            return score
        return -1.0
    except ValueError:
        return -1.0


def resolve_pairwise_winner(
    verdict_ab: str,
    verdict_ba: str,
    model_a: str,
    model_b: str,
) -> str:
    """
    Position swap 결과를 합쳐 최종 winner를 결정.

    논문 Section 3.4 conservative approach:
    - verdict_ab: [A, B] 순서일 때 판정 ("A" or "B" or "tie")
    - verdict_ba: [B, A] 순서로 swap 후 판정
      (BA 순서이므로 "A"는 실제로 model_b가 더 좋다는 의미)
    - 두 판정이 일치하면 해당 모델이 winner.
    - 불일치하면 "inconsistent" → aggregate에서 tie로 처리.

    왜 conservative approach인가:
    - 논문 Section 3.4: "only declare a win when an answer is preferred in both orders"
    - A100에서 비용 절감 목적으로 swap 없이 쓸 경우 이 함수 우회 가능.

    Args:
        verdict_ab: AB 순서 판정 ("A" | "B" | "tie" | "error")
        verdict_ba: BA 순서 판정 ("A" | "B" | "tie" | "error")
        model_a: 첫 번째 모델 ID (정규화 참조용)
        model_b: 두 번째 모델 ID

    Returns:
        model_a | model_b | "tie" | "inconsistent" | "error"
    """
    # 파싱 실패 케이스
    if verdict_ab == "error" or verdict_ba == "error":
        return "error"

    # AB 순서에서 A가 이기면 model_a가 이김
    # AB 순서에서 B가 이기면 model_b가 이김
    winner_ab = model_a if verdict_ab == "A" else (model_b if verdict_ab == "B" else "tie")

    # BA 순서에서 A가 이기면 실제로는 model_b가 이김 (순서가 바뀌었으므로)
    # BA 순서에서 B가 이기면 실제로는 model_a가 이김
    winner_ba = model_b if verdict_ba == "A" else (model_a if verdict_ba == "B" else "tie")

    if winner_ab == winner_ba:
        return winner_ab  # model_a, model_b, 또는 "tie"

    return "inconsistent"


# ===========================================================================
# 유틸리티
# ===========================================================================

def format_messages_for_log(messages: List[Dict[str, str]], max_chars: int = 500) -> str:
    """
    디버깅/로깅용 메시지 요약 포맷.

    프롬프트 전체를 로그에 쓰면 너무 길어 가독성이 떨어지므로
    각 role의 앞 max_chars 문자만 출력한다.

    Args:
        messages: ChatClient.chat()에 전달할 messages 리스트
        max_chars: 각 content의 최대 출력 문자 수

    Returns:
        사람이 읽기 좋은 요약 문자열
    """
    lines = []
    for m in messages:
        role = m.get("role", "?")
        content = m.get("content", "")
        truncated = content[:max_chars] + ("..." if len(content) > max_chars else "")
        lines.append(f"[{role}]: {truncated}")
    return "\n".join(lines)