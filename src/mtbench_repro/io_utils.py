"""Strict JSONL I/O and path helpers for pipeline records."""

from __future__ import annotations

import json
import hashlib
import fcntl
import logging
import math
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, List, Union


from mtbench_repro.schemas import (
    JudgmentPairwise,
    JudgmentSingle,
    MT_BENCH_CATEGORIES,
    ModelAnswer,
    MTBenchQuestion,
)

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]


def _reject_nonstandard_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON numeric constant: {value}")

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
                yield json.loads(
                    line,
                    parse_constant=_reject_nonstandard_json_constant,
                )
            except (json.JSONDecodeError, ValueError) as e:

                raise ValueError(
                    f"Invalid strict JSON at {path}:{line_num}: {e}"
                ) from e

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

            f.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
            count += 1

    logger.info(f"Wrote {count} records to {path}")
    return count

def write_jsonl_atomic(
    path: PathLike,
    records: Iterable[Dict[str, Any]],
) -> int:
    """Replace a JSONL file atomically after fully writing its new contents."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _exclusive_jsonl_lock(path):
        return _write_jsonl_atomic_unlocked(path, records)

@contextmanager
def _exclusive_jsonl_lock(path: Path):
    """Serialize read-modify-write operations for one JSONL output."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f".{path.name}.lock")
    with lock_path.open("a+", encoding="utf-8") as lock_stream:
        fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_stream.fileno(), fcntl.LOCK_UN)

def _write_jsonl_atomic_unlocked(
    path: Path,
    records: Iterable[Dict[str, Any]],
) -> int:
    """Write via a unique same-directory temp file; caller owns the lock."""
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    count = 0
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            for record in records:
                stream.write(
                    json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n"
                )
                count += 1
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    logger.info("Wrote %d records to %s", count, path)
    return count

def append_jsonl(path: PathLike, record: Dict[str, Any]) -> None:
    """Append one strict-JSON record to a JSONL file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")

def stable_fingerprint(value: Any) -> str:
    """Return a stable SHA-256 for JSON-compatible pipeline inputs."""
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()

def upsert_jsonl(
    path: PathLike,
    record: Dict[str, Any],
    key_fields: tuple[str, ...] = ("question_id",),
) -> None:
    """Atomically replace an execution unit instead of appending duplicates."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _exclusive_jsonl_lock(path):
        existing = list(read_jsonl(path)) if path.exists() else []
        record_key = tuple(record.get(field) for field in key_fields)
        kept = [
            item
            for item in existing
            if tuple(item.get(field) for field in key_fields) != record_key
        ]
        kept.append(record)
        _write_jsonl_atomic_unlocked(path, kept)

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
    questions: List[MTBenchQuestion] = []
    for record_number, data in enumerate(read_jsonl(path), start=1):
        try:
            question = MTBenchQuestion.from_dict(data)
        except (KeyError, TypeError) as exc:
            raise ValueError(
                f"Invalid question record {record_number} in {path}: "
                "question_id, category, and turns are required"
            ) from exc
        questions.append(question)
    seen_ids: set[int] = set()
    for question in questions:
        if (
            not isinstance(question.question_id, int)
            or isinstance(question.question_id, bool)
        ):
            raise ValueError(f"Invalid question_id in {path}: {question.question_id!r}")
        if question.question_id in seen_ids:
            raise ValueError(f"Duplicate question_id in {path}: {question.question_id}")
        seen_ids.add(question.question_id)
        if not isinstance(question.category, str) or not question.category.strip():
            raise ValueError(
                f"Invalid category for question_id={question.question_id} in {path}"
            )
        if (
            not isinstance(question.turns, list)
            or len(question.turns) != 2
            or not all(isinstance(turn, str) and turn.strip() for turn in question.turns)
        ):
            raise ValueError(
                f"question_id={question.question_id} must contain two nonempty turns"
            )
        if question.reference is not None:

            if (
                not isinstance(question.reference, list)
                or len(question.reference) != 2
                or not all(isinstance(reference, str) for reference in question.reference)
                or not any(reference.strip() for reference in question.reference)
            ):
                raise ValueError(
                    f"question_id={question.question_id} has an invalid reference"
                )

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
    judgments: List[JudgmentSingle] = []
    for record_number, data in enumerate(read_jsonl(path), start=1):
        try:
            judgment = JudgmentSingle.from_dict(data)
        except (KeyError, TypeError) as exc:
            raise ValueError(
                f"Invalid single judgment record {record_number} in {path}"
            ) from exc

        def valid_score(value: object) -> bool:
            return (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(float(value))
                and (value == -1 or 1 <= value <= 10)
            )

        valid_timestamp = (
            judgment.tstamp is None
            or (
                isinstance(judgment.tstamp, (int, float))
                and not isinstance(judgment.tstamp, bool)
                and math.isfinite(float(judgment.tstamp))
            )
        )
        if not (
            isinstance(judgment.question_id, int)
            and not isinstance(judgment.question_id, bool)
            and isinstance(judgment.model_id, str)
            and bool(judgment.model_id.strip())
            and isinstance(judgment.judge_id, str)
            and bool(judgment.judge_id.strip())
            and valid_score(judgment.score_turn1)
            and valid_score(judgment.score_turn2)
            and isinstance(judgment.judgment_turn1, str)
            and isinstance(judgment.judgment_turn2, str)
            and judgment.category in MT_BENCH_CATEGORIES
            and valid_timestamp
        ):
            raise ValueError(
                f"Invalid single judgment values in record {record_number} of {path}"
            )
        judgments.append(judgment)
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
    judgments: List[JudgmentPairwise] = []
    valid_verdicts = {"A", "B", "tie", "error"}
    for record_number, data in enumerate(read_jsonl(path), start=1):
        try:
            judgment = JudgmentPairwise.from_dict(data)
        except (KeyError, TypeError) as exc:
            raise ValueError(
                f"Invalid pairwise judgment record {record_number} in {path}"
            ) from exc

        if not (
            judgment.winner_ab in valid_verdicts
            and judgment.winner_ba in valid_verdicts
        ):
            resolved_winner = None
        elif "error" in {judgment.winner_ab, judgment.winner_ba}:
            resolved_winner = "error"
        else:
            winner_ab = (
                judgment.model_a
                if judgment.winner_ab == "A"
                else judgment.model_b
                if judgment.winner_ab == "B"
                else "tie"
            )
            winner_ba = (
                judgment.model_b
                if judgment.winner_ba == "A"
                else judgment.model_a
                if judgment.winner_ba == "B"
                else "tie"
            )
            resolved_winner = (
                winner_ab if winner_ab == winner_ba else "inconsistent"
            )
        valid_timestamp = (
            judgment.tstamp is None
            or (
                isinstance(judgment.tstamp, (int, float))
                and not isinstance(judgment.tstamp, bool)
                and math.isfinite(float(judgment.tstamp))
            )
        )
        if not (
            isinstance(judgment.question_id, int)
            and not isinstance(judgment.question_id, bool)
            and isinstance(judgment.model_a, str)
            and bool(judgment.model_a.strip())
            and isinstance(judgment.model_b, str)
            and bool(judgment.model_b.strip())
            and judgment.model_a != judgment.model_b
            and isinstance(judgment.judge_id, str)
            and bool(judgment.judge_id.strip())
            and judgment.winner == resolved_winner
            and isinstance(judgment.judgment_ab, str)
            and isinstance(judgment.judgment_ba, str)
            and judgment.turn == 2
            and not isinstance(judgment.turn, bool)
            and judgment.category in MT_BENCH_CATEGORIES
            and valid_timestamp
        ):
            raise ValueError(
                f"Invalid pairwise judgment values in record {record_number} of {path}"
            )
        judgments.append(judgment)
    logger.info(f"Loaded {len(judgments)} pairwise judgments from {path}")
    return judgments

def get_processed_ids(path: PathLike) -> set:
    """Return recorded question IDs, or an empty set when the file is absent."""
    path = Path(path)
    if not path.exists():
        return set()
    return {d["question_id"] for d in read_jsonl(path) if "question_id" in d}

def get_processed_inputs(path: PathLike) -> dict[int, str]:
    """Map question IDs to input hashes for hash-aware resume."""
    path = Path(path)
    if not path.exists():
        return {}
    return {
        int(record["question_id"]): str(record["input_sha256"])
        for record in read_jsonl(path)
        if "question_id" in record and record.get("input_sha256")
    }

def get_latest_records(path: PathLike) -> dict[int, Dict[str, Any]]:
    """Return the last parseable record for each integer question ID."""
    path = Path(path)
    if not path.exists():
        return {}
    records: dict[int, Dict[str, Any]] = {}
    for record in read_jsonl(path):
        try:
            question_id = int(record["question_id"])
        except (KeyError, TypeError, ValueError):
            continue
        records[question_id] = record
    return records

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
