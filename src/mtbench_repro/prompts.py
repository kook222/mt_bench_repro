"""FastChat-derived MT-Bench judge templates, builders, and parsers.

The English constants preserve the FastChat pair-v2, pair-v2-multi-turn,
single-v1, pair-math-v1-multi-turn, single-v1-multi-turn, and
single-math-v1-multi-turn templates. Korean constants translate the same
templates. The v3 protocols fingerprint the complete role-separated messages
built here.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional


_SYSTEM_PAIRWISE = (
    "Please act as an impartial judge and evaluate the quality of the responses "
    "provided by two AI assistants to the user question displayed below. "
    "You should choose the assistant that follows the user's instructions and "
    "answers the user's question better. Your evaluation should consider factors "
    "such as the helpfulness, relevance, accuracy, depth, creativity, and level "
    "of detail of their responses. Begin your evaluation by comparing the two "
    "responses and provide a short explanation. Avoid any positional biases and "
    "ensure that the order in which the responses were presented does not "
    "influence your decision. Do not allow the length of the responses to "
    "influence your evaluation. Do not favor certain names of the assistants. "
    "Be as objective as possible. After providing your explanation, output your "
    "final verdict by strictly following this format: \"[[A]]\" if assistant A "
    "is better, \"[[B]]\" if assistant B is better, and \"[[C]]\" for a tie."
)


_SYSTEM_PAIRWISE_MULTI = (
    "Please act as an impartial judge and evaluate the quality of the responses "
    "provided by two AI assistants to the user questions. You should choose the "
    "assistant that follows the user's instructions and answers the user's "
    "questions better. Your evaluation should consider factors such as the "
    "helpfulness, relevance, accuracy, depth, creativity, and level of detail of "
    "their responses. You should focus on who provides a better answer to the "
    "second user question. Begin your evaluation by comparing the responses of "
    "the two assistants and provide a short explanation. Avoid any positional "
    "biases and ensure that the order in which the responses were presented does "
    "not influence your decision. Do not allow the length of the responses to "
    "influence your evaluation. Do not favor certain names of the assistants. Be "
    "as objective as possible. After providing your explanation, output your "
    "final verdict by strictly following this format: \"[[A]]\" if assistant A "
    "is better, \"[[B]]\" if assistant B is better, and \"[[C]]\" for a tie."
)

_SYSTEM_HELPFUL = "You are a helpful assistant."


_INSTRUCTION_SINGLE = (
    "Please act as an impartial judge and evaluate the quality of the response "
    "provided by an AI assistant to the user question displayed below. Your "
    "evaluation should consider factors such as the helpfulness, relevance, "
    "accuracy, depth, creativity, and level of detail of the response. Begin "
    "your evaluation by providing a short explanation. Be as objective as "
    "possible. After providing your explanation, you must rate the response on a "
    "scale of 1 to 10 by strictly following this format: \"[[rating]]\", for "
    "example: \"Rating: [[5]]\"."
)

_INSTRUCTION_SINGLE_REFERENCE = (
    "Please act as an impartial judge and evaluate the quality of the response "
    "provided by an AI assistant to the user question displayed below. Your "
    "evaluation should consider correctness and helpfulness. You will be given a "
    "reference answer and the assistant's answer. Begin your evaluation by "
    "comparing the assistant's answer with the reference answer. Identify and "
    "correct any mistakes. Be as objective as possible. After providing your "
    "explanation, you must rate the response on a scale of 1 to 10 by strictly "
    "following this format: \"[[rating]]\", for example: \"Rating: [[5]]\"."
)


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


_SYSTEM_PAIRWISE_REFERENCE = (
    "Please act as an impartial judge and evaluate the quality of the responses "
    "provided by two AI assistants to the user question displayed below. Your "
    "evaluation should consider correctness and helpfulness. You will be given a "
    "reference answer, assistant A's answer, and assistant B's answer. Your job "
    "is to evaluate which assistant's answer is better. Begin your evaluation by "
    "comparing both assistants' answers with the reference answer. Identify and "
    "correct any mistakes. Avoid any positional biases and ensure that the order "
    "in which the responses were presented does not influence your decision. Do "
    "not allow the length of the responses to influence your evaluation. Do not "
    "favor certain names of the assistants. Be as objective as possible. After "
    "providing your explanation, output your final verdict by strictly following "
    "this format: \"[[A]]\" if assistant A is better, \"[[B]]\" if assistant B "
    "is better, and \"[[C]]\" for a tie."
)


_SYSTEM_PAIRWISE_REFERENCE_MULTI = (
    "Please act as an impartial judge and evaluate the quality of the responses "
    "provided by two AI assistants to the user questions. Your evaluation should "
    "consider correctness and helpfulness. You will be given reference answers, "
    "the assistant A's answers, the assistant B's answers. Your job is to "
    "determine which assistant provides correct and helpful answers to the second "
    "user question. Begin your evaluation by comparing both assistants' answers "
    "with the reference answers. Identify and correct any mistakes. Avoid any "
    "positional biases and ensure that the order in which the responses were "
    "presented does not influence your decision. Do not allow the length of the "
    "responses to influence your evaluation. Do not favor certain names of the "
    "assistants. Be as objective as possible. After providing your explanation, "
    "output your final verdict by strictly following this format: \"[[A]]\" if "
    "assistant A is better, \"[[B]]\" if assistant B is better, and \"[[C]]\" "
    "for a tie."
)


_SYSTEM_SINGLE_MULTI = (
    "Please act as an impartial judge and evaluate the quality of the response "
    "provided by an AI assistant to the user question displayed below. Your "
    "evaluation should consider factors such as the helpfulness, relevance, "
    "accuracy, depth, creativity, and level of detail of the response. Your "
    "evaluation should focus on the assistant's answer to the second user "
    "question. Begin your evaluation by providing a short explanation. Be as "
    "objective as possible. After providing your explanation, you must rate the "
    "response on a scale of 1 to 10 by strictly following this format: "
    "\"[[rating]]\", for example: \"Rating: [[5]]\"."
)


_SYSTEM_SINGLE_REFERENCE_MULTI = (
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


_SYSTEM_PAIRWISE_KO = (
    "당신은 공정한 평가자입니다. 아래 사용자 질문에 대해 두 AI 어시스턴트가 작성한 "
    "답변의 품질을 평가해 주세요. 사용자의 지시를 더 잘 따르고 질문에 더 적절하게 "
    "답한 어시스턴트를 선택하세요. 평가 시 답변의 유용성, 관련성, 정확성, 깊이, "
    "창의성, 세부 묘사 수준을 고려하세요. 두 답변을 비교하며 간략한 설명으로 평가를 "
    "시작하고, 최대한 객관적으로 판단하세요. 답변이 제시된 순서에 영향받지 말고, "
    "답변 길이나 어시스턴트 이름에도 치우치지 마세요. 설명을 마친 후, 반드시 다음 "
    "형식으로 최종 판정을 내리세요: 어시스턴트 A가 더 나으면 \"[[A]]\", "
    "어시스턴트 B가 더 나으면 \"[[B]]\", 동점이면 \"[[C]]\"."
)


_SYSTEM_HELPFUL_KO = "당신은 유용한 어시스턴트입니다."

_INSTRUCTION_SINGLE_KO = (
    "당신은 공정한 평가자입니다. 아래 사용자 질문에 대해 AI 어시스턴트가 작성한 "
    "답변의 품질을 평가해 주세요. 평가 시 답변의 유용성, 관련성, 정확성, 깊이, "
    "창의성, 세부 묘사 수준을 고려하세요. 간략한 설명으로 평가를 시작하고, 최대한 "
    "객관적으로 판단하세요. 설명을 마친 후, 반드시 다음 형식으로 1점부터 10점 "
    "사이의 점수를 매겨 주세요: \"[[rating]]\", 예시: \"Rating: [[5]]\"."
)

_INSTRUCTION_SINGLE_REFERENCE_KO = (
    "당신은 공정한 평가자입니다. 아래 사용자 질문에 대해 AI 어시스턴트가 "
    "작성한 답변의 품질을 평가해 주세요. 평가 시 정확성과 유용성을 고려하세요. "
    "참고 정답과 어시스턴트의 답변이 주어집니다. 어시스턴트의 답변을 참고 정답과 "
    "비교하고, 오류가 있다면 찾아 바로잡으며 평가를 시작하세요. 최대한 객관적으로 판단하세요. "
    "설명을 마친 후, 반드시 다음 형식으로 1점부터 10점 사이의 점수를 매겨 주세요: "
    "\"[[rating]]\", 예시: \"Rating: [[5]]\"."
)

_SYSTEM_PAIRWISE_MULTI_KO = (
    "당신은 공정한 평가자입니다. 아래 사용자의 질문들에 대해 두 AI 어시스턴트가 "
    "작성한 답변의 품질을 평가해 주세요. 사용자의 지시를 더 잘 따르고 질문들에 더 적절하게 "
    "답한 어시스턴트를 선택하세요. 유용성, 관련성, 정확성, 깊이, 창의성, 세부 묘사 수준을 "
    "고려하되, 특히 두 번째 사용자 질문에 더 나은 답을 제공한 쪽에 집중하세요. 두 답변을 비교하는 "
    "간략한 설명으로 평가를 시작하고, 제시 순서나 답변 길이, 어시스턴트 이름에 치우치지 마세요. "
    "최대한 객관적으로 판단한 후, 어시스턴트 A가 더 나으면 \"[[A]]\", B가 더 나으면 "
    "\"[[B]]\", 동점이면 \"[[C]]\"로 최종 판정하세요."
)

_SYSTEM_SINGLE_MULTI_KO = (
    "당신은 공정한 평가자입니다. 아래 사용자 질문에 대해 AI 어시스턴트가 작성한 "
    "답변의 품질을 평가해 주세요. 유용성, 관련성, 정확성, 깊이, 창의성, 세부 묘사 수준을 "
    "고려하되, 특히 두 번째 사용자 질문에 대한 어시스턴트의 답변에 집중하세요. 간략한 "
    "설명으로 평가를 시작하고 최대한 객관적으로 판단한 후, 반드시 \"[[rating]]\" 형식으로 "
    "1점부터 10점 사이의 점수를 매겨 주세요. 예시: \"Rating: [[5]]\"."
)

_SYSTEM_PAIRWISE_REFERENCE_MULTI_KO = (
    "당신은 공정한 평가자입니다. 아래 사용자의 질문들에 대해 두 AI 어시스턴트가 "
    "작성한 답변의 정확성과 유용성을 평가해 주세요. 참고 정답들과 A·B의 답변들이 주어지며, "
    "두 번째 사용자 질문에 정확하고 유용한 답을 제공한 쪽을 판단하세요. 두 답변을 참고 정답과 "
    "비교하고 오류를 찾아 바로잡으며 평가를 시작하세요. 제시 순서나 답변 길이, 어시스턴트 이름에 "
    "치우치지 말고 최대한 객관적으로 판단하세요. 설명 후 A가 더 나으면 \"[[A]]\", B가 더 나으면 "
    "\"[[B]]\", 동점이면 \"[[C]]\"로 최종 판정하세요."
)


_SYSTEM_PAIRWISE_MATH_COT_KO = (
    "당신은 공정한 평가자입니다. 아래 사용자 질문에 대해 두 AI 어시스턴트가 작성한 "
    "답변의 정확성과 유용성을 평가해 주세요. 어느 쪽이 더 나은지 판단하는 것이 "
    "당신의 역할입니다. 먼저 사용자 질문을 단계별로 직접 풀어보세요. 그런 다음 두 "
    "답변을 당신의 풀이와 비교하고, 오류가 있다면 찾아서 수정하세요. 답변이 제시된 "
    "순서에 영향받지 말고, 답변 길이나 어시스턴트 이름에도 치우치지 마세요. 설명을 "
    "마친 후, 반드시 다음 형식으로 최종 판정을 내리세요: 어시스턴트 A가 더 나으면 "
    "\"[[A]]\", 어시스턴트 B가 더 나으면 \"[[B]]\", 동점이면 \"[[C]]\"."
)


_SYSTEM_PAIRWISE_REFERENCE_KO = (
    "당신은 공정한 평가자입니다. 아래 사용자 질문에 대해 두 AI 어시스턴트가 작성한 "
    "답변의 정확성과 유용성을 평가해 주세요. 참고 정답, 어시스턴트 A의 답변, "
    "어시스턴트 B의 답변이 주어지며, 어느 쪽이 더 나은지 판단하는 것이 당신의 "
    "역할입니다. 먼저 두 답변을 참고 정답과 비교하고, 오류가 있다면 찾아서 "
    "수정하세요. 답변이 제시된 순서에 영향받지 말고, 답변 길이나 어시스턴트 이름에도 "
    "치우치지 마세요. 설명을 마친 후, 반드시 다음 형식으로 최종 판정을 내리세요: "
    "어시스턴트 A가 더 나으면 \"[[A]]\", 어시스턴트 B가 더 나으면 \"[[B]]\", "
    "동점이면 \"[[C]]\"."
)


_SYSTEM_SINGLE_REFERENCE_MULTI_KO = (
    "당신은 공정한 평가자입니다. 사용자 질문에 대해 AI 어시스턴트가 작성한 답변의 "
    "정확성과 유용성을 평가해 주세요. 참고 정답과 어시스턴트의 답변이 주어지며, "
    "평가는 두 번째 질문에 대한 어시스턴트의 답변에 집중해 주세요. 어시스턴트의 "
    "답변을 참고 정답과 비교하고, 오류가 있다면 찾아서 수정하세요. 최대한 객관적으로 "
    "판단한 후, 반드시 다음 형식으로 1점부터 10점 사이의 점수를 매겨 주세요: "
    "\"[[rating]]\", 예시: \"Rating: [[5]]\"."
)


def _sys(en_prompt: str, ko_prompt: str, lang: str) -> str:
    """lang에 따라 적절한 시스템 프롬프트 반환."""
    return ko_prompt if lang == "ko" else en_prompt

def build_pairwise_prompt(
    question: str,
    answer_a: str,
    answer_b: str,
    reference: Optional[str] = None,
    use_cot: bool = False,
    lang: str = "en",
) -> List[Dict[str, str]]:
    """
    Single-turn pairwise 비교 프롬프트 생성.

    reference가 있으면 reference-guided pairwise prompt, use_cot이면 CoT prompt,
    둘 다 없으면 pairwise prompt를 사용한다.

    Args:
        question: 1st turn 질문 텍스트
        answer_a: Assistant A의 답변
        answer_b: Assistant B의 답변
        reference: 참조 답변 (math/coding 전용, reference-guided pairwise prompt)
        use_cot: True면 CoT 프롬프트 사용
        lang: "en" (기본값) 또는 "ko" (한국어 judge 프롬프트)

    Returns:
        [{"role": "system", "content": ...}, {"role": "user", "content": ...}]
        형식의 messages 리스트 (ChatClient.chat()에 직접 전달 가능)
    """
    if reference is not None:
        system = _sys(_SYSTEM_PAIRWISE_REFERENCE, _SYSTEM_PAIRWISE_REFERENCE_KO, lang)
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
        system = _sys(_SYSTEM_PAIRWISE_MATH_COT, _SYSTEM_PAIRWISE_MATH_COT_KO, lang)
        user_content = (
            f"[User Question]\n{question}\n\n"
            f"[The Start of Assistant A's Answer]\n{answer_a}\n"
            f"[The End of Assistant A's Answer]\n\n"
            f"[The Start of Assistant B's Answer]\n{answer_b}\n"
            f"[The End of Assistant B's Answer]"
        )
    else:
        system = _sys(_SYSTEM_PAIRWISE, _SYSTEM_PAIRWISE_KO, lang)
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
    lang: str = "en",
) -> List[Dict[str, str]]:
    """
    Multi-turn pairwise 비교 프롬프트 생성 (multi-turn pairwise prompt).

    두 대화 전체를 하나의 프롬프트에 담아 judge가 2nd turn을
    평가하도록 한다.

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
        {
            "role": "system",
            "content": _sys(
                _SYSTEM_PAIRWISE_MULTI, _SYSTEM_PAIRWISE_MULTI_KO, lang
            ),
        },
        {"role": "user", "content": f"{conv_a}\n\n{conv_b}"},
    ]

def build_multiturn_pairwise_reference_prompt(
    turns: List[str],
    answers_a: List[str],
    answers_b: List[str],
    references: List[str],
    lang: str = "en",
) -> List[Dict[str, str]]:
    """
    Multi-turn reference-guided pairwise 프롬프트.

    reference-guided pairwise prompt와 multi-turn pairwise prompt를 결합:
    - reference answer(1st/2nd turn 모두)를 judge에게 제공
    - 두 모델의 전체 2-turn 대화를 하나의 프롬프트에 담음
    - judge가 reference 기준으로 두 모델의 정확성을 전체 대화 맥락에서 비교

    기존 단순화 방식(1st turn만, single-turn 포맷) 대비 차이:
    - 2nd turn 답변까지 함께 제공해 judge가 대화 전체를 평가
    - 두 개의 legacy reference 슬롯 중 비어 있지 않은 것만 제공

    Args:
        turns: [1st_turn_question, 2nd_turn_question]
        answers_a: [1st_answer_A, 2nd_answer_A]
        answers_b: [1st_answer_B, 2nd_answer_B]
        references: 정확히 두 개의 legacy 슬롯 [1st_reference, 2nd_reference].
            한 슬롯은 빈 문자열일 수 있지만 둘 다 비어 있을 수는 없음.

    Returns:
        messages 리스트
    """
    assert len(turns) == 2 and len(answers_a) == 2 and len(answers_b) == 2
    assert len(references) == 2, "MT-Bench reference는 두 턴 슬롯이 필요합니다."
    assert any(reference.strip() for reference in references), (
        "사용 가능한 reference가 최소 1개 필요합니다."
    )

    ref_turn1 = f"### User:\n{turns[0]}"
    if references[0].strip():
        ref_turn1 += f"\n### Reference answer:\n{references[0]}"
    ref_turn2 = f"### User:\n{turns[1]}"
    if references[1].strip():
        ref_turn2 += f"\n### Reference answer:\n{references[1]}"
    ref_block = (
        f"<|The Start of Reference Answer|>\n"
        f"{ref_turn1}\n"
        f"{ref_turn2}\n"
        f"<|The End of Reference Answer|>"
    )

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
        {
            "role": "system",
            "content": _sys(
                _SYSTEM_PAIRWISE_REFERENCE_MULTI,
                _SYSTEM_PAIRWISE_REFERENCE_MULTI_KO,
                lang,
            ),
        },
        {"role": "user", "content": f"{ref_block}\n\n{conv_a}\n\n{conv_b}"},
    ]

def build_single_prompt(
    question: str,
    answer: str,
    reference: Optional[str] = None,
    lang: str = "en",
) -> List[Dict[str, str]]:
    """
    Single-answer grading 프롬프트 생성 (single-grade prompt).

    각 turn마다 별도로 1~10점 척도의 평가 입력을 구성한다.

    Args:
        question: 해당 turn의 질문
        answer: 채점할 답변
        reference: 참조 답변 (있으면 single-grade prompt가 아닌 변형 사용)

    Returns:
        messages 리스트
    """
    system = _sys(_SYSTEM_HELPFUL, _SYSTEM_HELPFUL_KO, lang)
    if reference is not None:
        instruction = _sys(
            _INSTRUCTION_SINGLE_REFERENCE,
            _INSTRUCTION_SINGLE_REFERENCE_KO,
            lang,
        )
        user_content = (
            f"[Instruction]\n{instruction}\n\n"
            f"[Question]\n{question}\n\n"
            f"[The Start of Reference Answer]\n{reference}\n"
            f"[The End of Reference Answer]\n\n"
            f"[The Start of Assistant's Answer]\n{answer}\n"
            f"[The End of Assistant's Answer]"
        )
    else:
        instruction = _sys(_INSTRUCTION_SINGLE, _INSTRUCTION_SINGLE_KO, lang)
        user_content = (
            f"[Instruction]\n{instruction}\n\n"
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
    lang: str = "en",
) -> List[Dict[str, str]]:
    """
    Multi-turn single-answer grading 프롬프트 생성 (reference-guided single-grade prompt).

    reference answer와 전체 대화 맥락을 포함해 2nd turn 채점
    입력을 구성한다.

    Args:
        turns: [1st_turn_question, 2nd_turn_question]
        answers: [1st_answer, 2nd_answer]
        references: [1st_ref, 2nd_ref] (선택적)

    Returns:
        messages 리스트
    """
    assert len(turns) == 2 and len(answers) == 2

    if references is not None:
        assert len(references) == 2
        assert any(reference.strip() for reference in references)
        ref_turn1 = f"### User:\n{turns[0]}"
        if references[0].strip():
            ref_turn1 += f"\n### Reference answer:\n{references[0]}"
        ref_turn2 = f"### User:\n{turns[1]}"
        if references[1].strip():
            ref_turn2 += f"\n### Reference answer:\n{references[1]}"
        ref_block = (
            f"<|The Start of Reference Answer|>\n"
            f"{ref_turn1}\n"
            f"{ref_turn2}\n"
            f"<|The End of Reference Answer|>\n\n"
        )
        system = _sys(
            _SYSTEM_SINGLE_REFERENCE_MULTI,
            _SYSTEM_SINGLE_REFERENCE_MULTI_KO,
            lang,
        )
    else:
        ref_block = ""
        system = _sys(_SYSTEM_SINGLE_MULTI, _SYSTEM_SINGLE_MULTI_KO, lang)

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

def parse_pairwise_verdict(text: str) -> str:
    """
    Pairwise judge 응답에서 최종 판정을 파싱.

    Pairwise prompt의 출력 형식:
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

    matches = re.findall(r"\[\[([ABCabc])\]\]", text)
    if not matches:
        return "error"

    verdict = matches[-1].upper()
    if verdict == "C":
        return "tie"
    return verdict

def parse_single_score(text: str) -> float:
    """
    Single-answer grading 응답에서 점수를 파싱.

    Single-grade prompt의 출력 형식: "Rating: [[5]]"
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

    matches = re.findall(r"\[\[(\d+(?:\.\d+)?)\]\]", text)
    if not matches:

        matches = re.findall(r"[Rr]ating:\s*(\d+(?:\.\d+)?)", text)
    if not matches:

        matches = re.findall(r"[Rr]ating:\s*\*\*(\d+(?:\.\d+)?)\*\*", text)
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

    AB/BA 판정을 합치는 방식:
    - verdict_ab: [A, B] 순서일 때 판정 ("A" or "B" or "tie")
    - verdict_ba: [B, A] 순서로 swap 후 판정
      (BA 순서이므로 "A"는 실제로 model_b가 더 좋다는 의미)
    - 두 판정이 일치하면 해당 모델이 winner.
    - 불일치하면 "inconsistent" → 승자를 선언하지 않고 별도 집계.

    두 순서의 판정이 다르면 승자를 선언하지 않는다.

    Args:
        verdict_ab: AB 순서 판정 ("A" | "B" | "tie" | "error")
        verdict_ba: BA 순서 판정 ("A" | "B" | "tie" | "error")
        model_a: 첫 번째 모델 ID (정규화 참조용)
        model_b: 두 번째 모델 ID

    Returns:
        model_a | model_b | "tie" | "inconsistent" | "error"
    """

    if verdict_ab == "error" or verdict_ba == "error":
        return "error"

    winner_ab = model_a if verdict_ab == "A" else (model_b if verdict_ab == "B" else "tie")

    winner_ba = model_b if verdict_ba == "A" else (model_a if verdict_ba == "B" else "tie")

    if winner_ab == winner_ba:
        return winner_ab

    return "inconsistent"

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
