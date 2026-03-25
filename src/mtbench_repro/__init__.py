# src/mtbench_repro/__init__.py
"""
MT-Bench 평가 파이프라인 패키지.

왜 __init__.py가 필요한가:
- Python이 이 디렉토리를 패키지로 인식하려면 반드시 있어야 한다.
- 없으면 `from mtbench_repro.xxx import ...` 형태의 import가
  ModuleNotFoundError를 발생시킨다.
- 내용을 비워두지 않고 버전과 주요 공개 인터페이스를 명시해
  패키지 사용자가 어떤 모듈을 쓰면 되는지 바로 알 수 있게 한다.
"""

__version__ = "0.1.0"
__author__ = "MT-Bench Reproduction Project"

# 패키지 외부에서 자주 쓰는 타입만 최상위로 노출.
# judge_*.py, aggregate.py를 직접 import하지 않는 이유:
# 해당 모듈들은 CLI 엔트리포인트를 포함하므로 import 시
# side effect(logging 설정 등)가 발생할 수 있기 때문이다.
from mtbench_repro.schemas import (
    JudgmentPairwise,
    JudgmentSingle,
    ModelAnswer,
    MTBenchQuestion,
    MT_BENCH_CATEGORIES,
    REFERENCE_GUIDED_CATEGORIES,
)

__all__ = [
    "MTBenchQuestion",
    "ModelAnswer",
    "JudgmentSingle",
    "JudgmentPairwise",
    "MT_BENCH_CATEGORIES",
    "REFERENCE_GUIDED_CATEGORIES",
]