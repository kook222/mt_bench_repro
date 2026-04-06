# src/mtbench_repro/cli.py
"""
MT-Bench 파이프라인 통합 CLI 엔트리포인트.

왜 별도 cli.py가 필요한가:
- 각 모듈을 python -m mtbench_repro.generate 처럼 개별 실행할 수 있지만,
  파이프라인 전체를 하나의 진입점으로 관리하면 A100 서버에서
  단일 커맨드로 전체 흐름을 실행할 수 있다.
- 서브커맨드 구조: `python -m mtbench_repro.cli generate --mock` 처럼 사용.

사용 예시:
    python -m mtbench_repro.cli generate --model-id vicuna-13b --mock
    python -m mtbench_repro.cli judge-single --model-id vicuna-13b --mock
    python -m mtbench_repro.cli judge-pairwise --model-a vicuna-13b --model-b llama-13b --mock
    python -m mtbench_repro.cli judge-reference --model-id vicuna-13b --mode single --mock
    python -m mtbench_repro.cli aggregate --judgments-dir data/judgments/
"""

from __future__ import annotations

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 공통 인자 빌더 (중복 제거)
# ---------------------------------------------------------------------------

def _add_common_args(parser: argparse.ArgumentParser) -> None:
    """여러 서브커맨드에서 공통으로 쓰는 인자를 한 곳에서 정의."""
    parser.add_argument(
        "--provider", type=str,
        choices=["openai_compatible", "anthropic"],
        default="openai_compatible",
        help="judge/generate API provider",
    )
    parser.add_argument(
        "--questions", type=str,
        default="data/mt_bench_questions.jsonl",
        help="MT-Bench 질문 JSONL 경로",
    )
    parser.add_argument(
        "--answers-dir", type=str,
        default="data/answers/",
        help="답변 JSONL 저장/로드 디렉토리",
    )
    parser.add_argument(
        "--output-dir", type=str,
        default="data/judgments/",
        help="판정 결과 저장 디렉토리",
    )
    parser.add_argument(
        "--judge-model", type=str,
        default="gpt-4",
        help="judge로 사용할 모델명",
    )
    parser.add_argument(
        "--api-key", type=str,
        default=None,
        help="provider용 API 키 (없으면 provider별 환경변수 사용)",
    )
    parser.add_argument(
        "--base-url", type=str,
        default=None,
        help="provider용 base URL (Anthropic native SDK는 https://api.anthropic.com 사용)",
    )
    parser.add_argument(
        "--openai-api-key", type=str,
        default=None,
        help="구버전 호환용 alias (--api-key 권장)",
    )
    parser.add_argument(
        "--openai-base-url", type=str,
        default=None,
        help="구버전 호환용 alias (--base-url 권장)",
    )
    parser.add_argument(
        "--sleep", type=float,
        default=1.0,
        help="API 호출 간 대기 시간 (초)",
    )
    parser.add_argument(
        "--mock", action="store_true",
        help="mock client 사용 (API 없이 로컬 테스트)",
    )
    parser.add_argument(
        "--no-resume", action="store_true",
        help="resume 비활성화 (처음부터 다시 실행)",
    )


def _build_client(args: argparse.Namespace):
    """argparse 결과에서 ChatClient를 생성하는 헬퍼."""
    from mtbench_repro.client import ChatClient
    if args.mock:
        logger.info("Mock 모드로 ChatClient 생성")
        return ChatClient.mock()

    provider = getattr(args, "provider", "openai_compatible")
    api_key = getattr(args, "api_key", None) or getattr(args, "openai_api_key", None)
    base_url = getattr(args, "base_url", None) or getattr(args, "openai_base_url", None)
    if not base_url:
        if provider == "anthropic":
            base_url = "https://api.anthropic.com"
        else:
            base_url = "https://api.openai.com/v1"
    return ChatClient(
        api_key=api_key,
        base_url=base_url,
        default_model=args.judge_model,
        provider=provider,
    )


# ---------------------------------------------------------------------------
# 서브커맨드: generate
# ---------------------------------------------------------------------------

def cmd_generate(args: argparse.Namespace) -> None:
    from mtbench_repro.client import ChatClient
    from mtbench_repro.generate import run_generation

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


def add_generate_parser(subparsers) -> None:
    p = subparsers.add_parser("generate", help="모델 답변 생성")
    _add_common_args(p)
    p.add_argument("--model-id", type=str, required=True,
                   help="생성 모델 ID (vLLM served-model-name과 일치)")
    p.add_argument("--vllm-host", type=str, default="localhost")
    p.add_argument("--vllm-port", type=int, default=8000)
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--max-tokens", type=int, default=1024)
    p.set_defaults(func=cmd_generate)


# ---------------------------------------------------------------------------
# 서브커맨드: judge-single
# ---------------------------------------------------------------------------

def cmd_judge_single(args: argparse.Namespace) -> None:
    from mtbench_repro.judge_single import run_judge_single
    client = _build_client(args)
    run_judge_single(
        questions_path=args.questions,
        answers_dir=args.answers_dir,
        output_dir=args.output_dir,
        model_id=args.model_id,
        judge_client=client,
        judge_model=args.judge_model,
        sleep_between_calls=args.sleep,
        resume=not args.no_resume,
    )


def add_judge_single_parser(subparsers) -> None:
    p = subparsers.add_parser("judge-single", help="Single-answer grading (Figure 6)")
    _add_common_args(p)
    p.add_argument("--model-id", type=str, required=True,
                   help="채점 대상 모델 ID")
    p.set_defaults(func=cmd_judge_single)


# ---------------------------------------------------------------------------
# 서브커맨드: judge-pairwise
# ---------------------------------------------------------------------------

def cmd_judge_pairwise(args: argparse.Namespace) -> None:
    from mtbench_repro.judge_pairwise import run_all_pairs, run_judge_pairwise
    client = _build_client(args)

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
        )
    else:
        logger.error("--model-a/--model-b 또는 --models 중 하나를 지정하세요.")
        sys.exit(1)


def add_judge_pairwise_parser(subparsers) -> None:
    p = subparsers.add_parser("judge-pairwise",
                              help="Pairwise comparison + swap (Figure 5, 9)")
    _add_common_args(p)
    p.add_argument("--model-a", type=str, default=None)
    p.add_argument("--model-b", type=str, default=None)
    p.add_argument("--models", type=str, nargs="+", default=None,
                   help="모든 pairs를 실행할 모델 목록")
    p.set_defaults(func=cmd_judge_pairwise)


# ---------------------------------------------------------------------------
# 서브커맨드: judge-reference
# ---------------------------------------------------------------------------

def cmd_judge_reference(args: argparse.Namespace) -> None:
    from mtbench_repro.judge_reference import (
        run_judge_reference_pairwise,
        run_judge_reference_single,
    )
    client = _build_client(args)

    if args.mode == "single":
        if not args.model_id:
            logger.error("single 모드에서는 --model-id가 필요합니다.")
            sys.exit(1)
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
        )
    else:
        if not (args.model_a and args.model_b):
            logger.error("pairwise 모드에서는 --model-a와 --model-b가 필요합니다.")
            sys.exit(1)
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
        )


def add_judge_reference_parser(subparsers) -> None:
    p = subparsers.add_parser("judge-reference",
                              help="Reference-guided grading (Figure 8, 10)")
    _add_common_args(p)
    p.add_argument("--mode", choices=["single", "pairwise"], default="single")
    p.add_argument("--model-id", type=str, default=None)
    p.add_argument("--model-a", type=str, default=None)
    p.add_argument("--model-b", type=str, default=None)
    p.add_argument("--categories", type=str, nargs="+", default=None,
                   help="대상 카테고리 (기본: math reasoning coding)")
    p.set_defaults(func=cmd_judge_reference)


# ---------------------------------------------------------------------------
# 서브커맨드: aggregate
# ---------------------------------------------------------------------------

def cmd_aggregate(args: argparse.Namespace) -> None:
    from mtbench_repro.aggregate import run_aggregate
    run_aggregate(
        judgments_dir=args.judgments_dir,
        model_ids=args.models,
        output_csv=args.output_csv,
        questions_path=args.questions_path,
        include_partial=args.include_partial,
        output_ref_csv=args.output_ref_csv,
    )


def add_aggregate_parser(subparsers) -> None:
    p = subparsers.add_parser("aggregate", help="결과 집계 및 trend 분석")
    p.add_argument("--judgments-dir", type=str, default="data/judgments/")
    p.add_argument("--questions-path", type=str, default=None,
                   help="질문 JSONL 경로 (지정 시 complete coverage 검증 수행)")
    p.add_argument("--models", type=str, nargs="+", default=None)
    p.add_argument("--output-csv", type=str, default=None)
    p.add_argument("--output-ref-csv", type=str, default=None)
    p.add_argument("--include-partial", action="store_true",
                   help="불완전한 partial 결과도 집계에 포함")
    p.set_defaults(func=cmd_aggregate)


# ---------------------------------------------------------------------------
# 메인 파서 조립
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mtbench_repro",
        description=(
            "MT-Bench 평가 파이프라인 CLI\n"
            "논문: Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena\n\n"
            "실행 방법: PYTHONPATH=src python -m mtbench_repro.cli <subcommand>"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version", action="version", version="mtbench_repro 0.1.0"
    )
    subparsers = parser.add_subparsers(
        title="서브커맨드",
        dest="command",
        metavar="<command>",
    )
    subparsers.required = True

    add_generate_parser(subparsers)
    add_judge_single_parser(subparsers)
    add_judge_pairwise_parser(subparsers)
    add_judge_reference_parser(subparsers)
    add_aggregate_parser(subparsers)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
