"""Dataclasses for MT-Bench questions, answers, and judgments."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


@dataclass
class MTBenchQuestion:
    """
    MT-Bench 단일 질문 항목.

    Attributes:
        question_id: 질문 고유 ID (FastChat 형식: 정수)
        category: 8개 카테고리 중 하나
                  (writing, roleplay, extraction, reasoning,
                   math, coding, stem, humanities)
        turns: 1st turn과 2nd turn 질문 텍스트 리스트
        reference: reference-guided judge에 사용할 참조 답변 리스트
    """
    question_id: int
    category: str
    turns: List[str]
    reference: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def has_reference_for_turn(self, turn_index: int) -> bool:
        """Return whether the requested turn has a non-empty reference answer."""
        return bool(
            self.reference is not None
            and 0 <= turn_index < len(self.reference)
            and isinstance(self.reference[turn_index], str)
            and self.reference[turn_index].strip()
        )

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MTBenchQuestion":
        return cls(
            question_id=d["question_id"],
            category=d["category"],
            turns=d["turns"],
            reference=d.get("reference"),
        )

@dataclass
class ModelAnswer:
    """
    단일 질문에 대한 단일 모델의 답변.

    Attributes:
        question_id: 대응하는 질문 ID
        model_id: 모델 식별자
        choices: 생성된 답변 리스트
                 각 choice는 {"index": int, "turns": List[str]} 형식
                 일반적으로 choices[0]["turns"]가 실제 사용하는 답변
        tstamp: 생성 타임스탬프 (재현 추적용)
    """
    question_id: int
    model_id: str
    choices: List[Dict[str, Any]]
    tstamp: Optional[float] = None
    input_sha256: Optional[str] = None

    def get_turns(self, choice_idx: int = 0) -> List[str]:
        """
        choices[choice_idx]["turns"]를 반환하는 편의 메서드.
        judge 파일에서 반복적으로 쓰이므로 인터페이스를 단순화한다.
        """
        return self.choices[choice_idx]["turns"]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ModelAnswer":
        return cls(
            question_id=d["question_id"],
            model_id=d["model_id"],
            choices=d["choices"],
            tstamp=d.get("tstamp"),
            input_sha256=d.get("input_sha256"),
        )

@dataclass
class JudgmentSingle:
    """
    Single-answer grading 결과.
    Single-grade prompt의 1~10점 척도와 ``[[rating]]`` 파싱 결과.

    Attributes:
        question_id: 판정 대상 질문 ID
        model_id: 채점 대상 모델
        judge_id: 판정에 사용한 judge 모델
        score_turn1: 1st turn 점수 (1~10, 파싱 실패 시 -1)
        score_turn2: 2nd turn 점수 (1~10, 파싱 실패 시 -1)
        judgment_turn1: 1st turn에 대한 judge의 원문 응답 (설명 포함)
        judgment_turn2: 2nd turn에 대한 judge의 원문 응답
        category: 집계 분석용 카테고리 (aggregate.py에서 활용)
        tstamp: 판정 타임스탬프
    """
    question_id: int
    model_id: str
    judge_id: str
    score_turn1: float
    score_turn2: float
    judgment_turn1: str
    judgment_turn2: str
    category: str = ""
    tstamp: Optional[float] = None
    input_sha256: Optional[str] = None

    @property
    def avg_score(self) -> Optional[float]:
        """
        ``(turn1 + turn2) / 2``를 한 문항의 점수로 반환한다.
        파싱 실패(-1)가 있으면 NaN으로 처리해 집계를 오염시키지 않는다.
        """
        if self.score_turn1 < 0 or self.score_turn2 < 0:
            return None
        return (self.score_turn1 + self.score_turn2) / 2.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["avg_score"] = self.avg_score
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "JudgmentSingle":
        return cls(
            question_id=d["question_id"],
            model_id=d["model_id"],
            judge_id=d["judge_id"],
            score_turn1=d["score_turn1"],
            score_turn2=d["score_turn2"],
            judgment_turn1=d["judgment_turn1"],
            judgment_turn2=d["judgment_turn2"],
            category=d.get("category", ""),
            tstamp=d.get("tstamp"),
            input_sha256=d.get("input_sha256"),
        )

@dataclass
class JudgmentPairwise:
    """
    Pairwise comparison 결과.
    A / B / tie 판정을 저장하고 swap으로 position bias를 점검한다.

    Attributes:
        question_id: 판정 대상 질문 ID
        model_a: 첫 번째 모델 ID
        model_b: 두 번째 모델 ID
        judge_id: judge 모델 ID
        winner: 승리한 model_id / "tie" / "inconsistent" / "error"
                - "inconsistent": swap 후 결과가 달라진 경우
                  주 승률에서는 0.5/0.5 무승부로, 별도
                  consistent-only 민감도 지표에서는 제외
        judgment_ab: model_a가 먼저인 경우 judge 원문 응답
        judgment_ba: model_b가 먼저인 경우 judge 원문 응답 (swap 결과)
        winner_ab: swap 전 위치 기준 판정 ("A" / "B" / "tie" / "error")
        winner_ba: swap 후 위치 기준 판정 ("A" / "B" / "tie" / "error")
        turn: 1 또는 2 (MT-Bench 2-turn 중 어느 turn 기준)
        category: 집계용 카테고리
        tstamp: 판정 타임스탬프
    """
    question_id: int
    model_a: str
    model_b: str
    judge_id: str
    winner: str
    judgment_ab: str
    judgment_ba: str
    winner_ab: str
    winner_ba: str
    turn: int = 2
    category: str = ""
    tstamp: Optional[float] = None
    input_sha256: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "JudgmentPairwise":
        return cls(
            question_id=d["question_id"],
            model_a=d["model_a"],
            model_b=d["model_b"],
            judge_id=d["judge_id"],
            winner=d["winner"],
            judgment_ab=d["judgment_ab"],
            judgment_ba=d["judgment_ba"],
            winner_ab=d["winner_ab"],
            winner_ba=d["winner_ba"],
            turn=d.get("turn", 2),
            category=d.get("category", ""),
            tstamp=d.get("tstamp"),
            input_sha256=d.get("input_sha256"),
        )

MT_BENCH_CATEGORIES: List[str] = [
    "writing",
    "roleplay",
    "extraction",
    "reasoning",
    "math",
    "coding",
    "stem",
    "humanities",
]


REFERENCE_GUIDED_CATEGORIES: List[str] = ["math", "reasoning", "coding"]
