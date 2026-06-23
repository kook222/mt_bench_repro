# src/mtbench_repro/io_utils.py
"""
JSONL 기반 파일 입출력 유틸리티.

왜 io_utils.py를 schemas.py와 분리하는가:
- schemas.py는 순수 데이터 구조 정의만 담당하고,
  파일 I/O 로직(경로 처리, 인코딩, 에러 핸들링)은 별도로 관리하면
  schemas를 import해도 파일 시스템 의존성이 생기지 않는다.
- JSONL 포맷을 선택한 이유: 논문 저자들의 FastChat 구현과 호환되고,
  대용량 답변 파일을 한 줄씩 스트리밍할 수 있어 메모리 효율이 좋다.
- 각 함수가 Path 객체와 str 모두 받는 이유:
  노트북(str 경로)과 스크립트(Path 객체) 모두에서 사용하기 때문이다.

수정 이력:
- from schemas import → from mtbench_repro.schemas import 로 패키지 경로 통일.
  실행 방식이 `python -m mtbench_repro.xxx` 또는
  PYTHONPATH=src 기반이므로 절대 패키지 경로가 필요하다.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, List, Optional, Union

# 반드시 패키지 절대 경로로 import해야 한다.
# `from schemas import` 처럼 쓰면 python -m 실행 시
# ModuleNotFoundError가 발생한다.
from mtbench_repro.schemas import (
    JudgmentPairwise,
    JudgmentSingle,
    ModelAnswer,
    MTBenchQuestion,
)

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]


# ---------------------------------------------------------------------------
# 기본 JSONL 읽기/쓰기
# ---------------------------------------------------------------------------

def read_jsonl(path: PathLike) -> Generator[Dict[str, Any], None, None]:
    """
    JSONL 파일을 한 줄씩 읽어 dict를 yield하는 제너레이터.

    제너레이터를 쓰는 이유:
    - 답변 파일이 수천 행에 달할 수 있으므로 전체를 메모리에 올리지 않는다.
    - 빈 줄이나 주석(#)은 무시해 FastChat 데이터와 호환성을 유지한다.

    Args:
        path: JSONL 파일 경로

    Yields:
        파싱된 JSON dict

    Raises:
        FileNotFoundError: 파일이 없을 경우
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"JSONL file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                # 한 줄 파싱 실패가 전체 파이프라인을 멈추면 안 되므로 warn 후 skip
                logger.warning(f"JSON decode error at {path}:{line_num}: {e}")


def write_jsonl(
    path: PathLike,
    records: Iterable[Dict[str, Any]],
    mode: str = "w",
) -> int:
    """
    dict 이터러블을 JSONL 파일로 저장.

    Args:
        path: 저장 경로 (부모 디렉토리가 없으면 자동 생성)
        records: 저장할 dict 이터러블
        mode: "w"(덮어쓰기) 또는 "a"(추가). 재실행 안정성을 위해 기본은 "w"

    Returns:
        저장된 레코드 수
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with open(path, mode, encoding="utf-8") as f:
        for record in records:
            # ensure_ascii=False: 한글/특수문자 그대로 저장 (가독성)
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1

    logger.info(f"Wrote {count} records to {path}")
    return count


def append_jsonl(path: PathLike, record: Dict[str, Any]) -> None:
    """
    단일 record를 JSONL 파일에 추가 (judge 실시간 저장용).

    왜 필요한가:
    - judge 파이프라인에서 API 호출 실패 시 이미 완료된 결과를 잃지 않기 위해
      한 건씩 즉시 디스크에 flush한다.
    - 재실행 시 이미 처리된 question_id를 skip하는 로직과 함께 쓰인다.

    Args:
        path: 대상 JSONL 파일 경로
        record: 저장할 dict
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# 도메인 객체 로더 (schemas.py 타입과 연동)
# ---------------------------------------------------------------------------

def load_questions(path: PathLike) -> List[MTBenchQuestion]:
    """
    JSONL 파일에서 MTBenchQuestion 리스트 로드.

    FastChat 공식 mt_bench_questions.jsonl 형식:
    {"question_id": 81, "category": "writing", "turns": [...], "reference": [...]}

    Args:
        path: mt_bench_questions.jsonl 경로

    Returns:
        MTBenchQuestion 리스트 (question_id 순으로 정렬)
    """
    questions = [MTBenchQuestion.from_dict(d) for d in read_jsonl(path)]
    # 일관된 순서 보장 — 셔플된 파일이 들어와도 재현 가능하게
    questions.sort(key=lambda q: q.question_id)
    logger.info(f"Loaded {len(questions)} questions from {path}")
    return questions


def load_answers(path: PathLike) -> Dict[int, ModelAnswer]:
    """
    JSONL 파일에서 ModelAnswer 로드, question_id를 키로 하는 dict 반환.

    dict로 반환하는 이유:
    - judge 파이프라인에서 question_id로 O(1) 조회가 필요하기 때문이다.
    - 같은 question_id가 중복되면 마지막 항목으로 덮어쓴다 (경고 출력).

    Args:
        path: {model_name}.jsonl 답변 파일 경로

    Returns:
        {question_id: ModelAnswer} dict
    """
    result: Dict[int, ModelAnswer] = {}
    for d in read_jsonl(path):
        answer = ModelAnswer.from_dict(d)
        if answer.question_id in result:
            logger.warning(
                f"Duplicate question_id {answer.question_id} in {path}. Overwriting."
            )
        result[answer.question_id] = answer
    logger.info(f"Loaded {len(result)} answers from {path}")
    return result


def load_single_judgments(path: PathLike) -> List[JudgmentSingle]:
    """
    Single-answer grading 결과 JSONL 로드.

    Args:
        path: single_grade/{model_name}.jsonl 경로

    Returns:
        JudgmentSingle 리스트
    """
    judgments = [JudgmentSingle.from_dict(d) for d in read_jsonl(path)]
    logger.info(f"Loaded {len(judgments)} single judgments from {path}")
    return judgments


def load_pairwise_judgments(path: PathLike) -> List[JudgmentPairwise]:
    """
    Pairwise comparison 결과 JSONL 로드.

    Args:
        path: pairwise/{model_a}_vs_{model_b}.jsonl 경로

    Returns:
        JudgmentPairwise 리스트
    """
    judgments = [JudgmentPairwise.from_dict(d) for d in read_jsonl(path)]
    logger.info(f"Loaded {len(judgments)} pairwise judgments from {path}")
    return judgments


# ---------------------------------------------------------------------------
# 재실행 안전성: 이미 처리된 question_id 확인
# ---------------------------------------------------------------------------

def get_processed_ids(path: PathLike) -> set:
    """
    이미 처리된 question_id 집합을 반환.

    왜 필요한가:
    - A100 서버에서 judge 도중 API 타임아웃/오류가 발생해 프로세스가 죽으면
      처음부터 다시 실행하면 비용 낭비다.
    - 출력 파일에서 기존 question_id를 읽어 skip 대상으로 쓴다.

    Args:
        path: 체크할 JSONL 파일 경로

    Returns:
        이미 처리된 question_id의 set. 파일이 없으면 빈 set 반환.
    """
    path = Path(path)
    if not path.exists():
        return set()
    return {d["question_id"] for d in read_jsonl(path) if "question_id" in d}


# ---------------------------------------------------------------------------
# 답변 디렉토리 유틸리티
# ---------------------------------------------------------------------------

def get_answer_path(answers_dir: PathLike, model_id: str) -> Path:
    """
    모델 ID에서 답변 파일 경로를 생성.
    모델 이름의 '/'를 '_'로 치환해 파일명 안전성 확보.

    Args:
        answers_dir: data/answers/ 디렉토리
        model_id: 모델 식별자 (예: "meta-llama/Llama-2-13b-chat-hf")

    Returns:
        data/answers/meta-llama_Llama-2-13b-chat-hf.jsonl
    """
    safe_name = model_id.replace("/", "_")
    return Path(answers_dir) / f"{safe_name}.jsonl"


def list_available_models(answers_dir: PathLike) -> List[str]:
    """
    지정 디렉토리에서 사용 가능한 모델 ID 목록 반환.
    파이프라인 자동화 시 어떤 모델 결과가 있는지 확인하는 데 쓴다.

    Args:
        answers_dir: data/answers/ 또는 data/judgments/single_grade/ 디렉토리

    Returns:
        파일명(확장자 제외) 리스트
    """
    answers_dir = Path(answers_dir)
    if not answers_dir.exists():
        return []
    return [p.stem for p in sorted(answers_dir.glob("*.jsonl"))]