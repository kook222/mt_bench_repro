# src/schemas.py
"""
MT-Bench 재현 파이프라인 전체에서 사용하는 데이터 스키마 정의.

왜 별도 파일로 분리하는가:
- io_utils.py, judge_*.py, aggregate.py가 모두 동일한 필드 이름을 참조하므로
  한 곳에서 구조를 확정해두면 필드명 불일치 버그를 방지할 수 있다.
- dataclass를 쓰는 이유: TypedDict보다 .attribute 접근과 기본값 설정이 직관적이고,
  asdict()로 JSONL 직렬화가 간단하기 때문이다.
- Optional 필드는 파이프라인 단계마다 채워지는 구조를 반영한다.
  (예: judgment는 judge 단계 전까지 None)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# MT-Bench 질문 스키마
# 논문 Section 2.2: 80개 질문, 8 카테고리, 각 2-turn
# FastChat 공식 데이터 형식과 호환되도록 필드를 맞춤
# ---------------------------------------------------------------------------

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
               논문 Section 2.2에서 모든 질문은 정확히 2-turn
        reference: 참조 답변 리스트 (reference-guided judge 전용, 선택적)
                   논문 Section 3.4, Figure 8에서 수학/추론 문제에만 사용
    """
    question_id: int
    category: str
    turns: List[str]
    reference: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MTBenchQuestion":
        return cls(
            question_id=d["question_id"],
            category=d["category"],
            turns=d["turns"],
            reference=d.get("reference"),
        )


# ---------------------------------------------------------------------------
# 모델 답변 스키마
# 논문 Section 4.1: 6개 모델의 80문항 × 2-turn 답변 생성
# ---------------------------------------------------------------------------

@dataclass
class ModelAnswer:
    """
    단일 질문에 대한 단일 모델의 답변.

    Attributes:
        question_id: 대응하는 질문 ID
        model_id: 모델 식별자 (예: "vicuna-13b", "gpt-4")
        choices: 생성된 답변 리스트
                 각 choice는 {"index": int, "turns": List[str]} 형식
                 일반적으로 choices[0]["turns"]가 실제 사용하는 답변
                 논문에서는 단일 답변을 사용하므로 choices는 길이 1
        tstamp: 생성 타임스탬프 (재현 추적용)
    """
    question_id: int
    model_id: str
    choices: List[Dict[str, Any]]
    tstamp: Optional[float] = None

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
        )


# ---------------------------------------------------------------------------
# Judge 판정 결과 스키마 (pairwise / single 공용)
# 논문 Section 3.1: 3가지 judge 방식 모두 이 스키마로 결과를 저장
# ---------------------------------------------------------------------------

@dataclass
class JudgmentSingle:
    """
    Single-answer grading 결과.
    논문 Figure 6 기반: 1~10점 척도, [[rating]] 파싱.

    Attributes:
        question_id: 판정 대상 질문 ID
        model_id: 채점 대상 모델
        judge_id: 판정에 사용한 judge 모델 (예: "gpt-4")
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

    @property
    def avg_score(self) -> float:
        """
        논문 Table 8: MT-Bench Score = 160턴 평균.
        즉 (turn1 + turn2) / 2 가 한 문항의 점수.
        파싱 실패(-1)가 있으면 NaN으로 처리해 집계를 오염시키지 않는다.
        """
        if self.score_turn1 < 0 or self.score_turn2 < 0:
            return float("nan")
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
        )


@dataclass
class JudgmentPairwise:
    """
    Pairwise comparison 결과.
    논문 Figure 5/9 기반: A / B / tie 판정, swap으로 position bias 완화.

    Attributes:
        question_id: 판정 대상 질문 ID
        model_a: 첫 번째 모델 ID
        model_b: 두 번째 모델 ID
        judge_id: judge 모델 ID
        winner: "A" / "B" / "tie" / "inconsistent"
                - "inconsistent": swap 후 결과가 달라진 경우
                  논문 Section 3.4의 conservative approach 반영:
                  swap 후 불일치 → tie로 처리
        judgment_ab: model_a가 먼저인 경우 judge 원문 응답
        judgment_ba: model_b가 먼저인 경우 judge 원문 응답 (swap 결과)
        winner_ab: swap 전 판정 ("A" / "B" / "tie")
        winner_ba: swap 후 판정 (model 순서 기준 원래 이름으로 정규화)
        turn: 1 또는 2 (MT-Bench 2-turn 중 어느 turn 기준)
        category: 집계용 카테고리
        tstamp: 판정 타임스탬프
    """
    question_id: int
    model_a: str
    model_b: str
    judge_id: str
    winner: str  # "A" | "B" | "tie" | "inconsistent"
    judgment_ab: str
    judgment_ba: str
    winner_ab: str
    winner_ba: str
    turn: int = 2  # 논문은 2nd turn 기준 pairwise 사용
    category: str = ""
    tstamp: Optional[float] = None

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
        )


# ---------------------------------------------------------------------------
# 카테고리 상수
# 논문 Section 2.2, Table 7 기준 8개 카테고리
# ---------------------------------------------------------------------------

MT_BENCH_CATEGORIES: List[str] = [
    "writing",
    "roleplay",
    "extraction",
    "reasoning",
    "math",
    "coding",
    "stem",       # 논문에서 "knowledge I (STEM)"
    "humanities",  # 논문에서 "knowledge II (humanities/social science)"
]

# 논문 Section 3.4, Table 4:
# reference-guided judge가 필요한 카테고리 (math, reasoning은 CoT/reference 효과 큼)
REFERENCE_GUIDED_CATEGORIES: List[str] = ["math", "reasoning", "coding"]