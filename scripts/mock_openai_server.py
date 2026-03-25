#!/usr/bin/env python3
# scripts/mock_openai_server.py
"""
로컬 Mock OpenAI-compatible API 서버 (Flask 기반).

왜 필요한가:
- ChatClient의 --mock 플래그는 HTTP 호출 없이 내부적으로 더미 응답을 반환한다.
- 이 서버는 실제 HTTP 요청/응답 흐름을 테스트할 때 사용한다.
  (네트워크 오류, 타임아웃, rate limit 재현 등)
- vLLM 서버를 띄울 수 없는 환경에서 --openai-base-url http://localhost:9999/v1 로
  ChatClient를 연결해 실제 API 호출 경로를 검증할 수 있다.

실행:
    python scripts/mock_openai_server.py --port 9999

연결:
    python -m mtbench_repro.cli judge-single \
      --openai-base-url http://localhost:9999/v1 \
      --openai-api-key EMPTY \
      --judge-model gpt-4 \
      --model-id vicuna-13b
"""

from __future__ import annotations

import argparse
import json
import re
import time
import uuid

try:
    from flask import Flask, jsonify, request  # type: ignore[import-untyped]
except ImportError:
    raise ImportError(
        "Flask가 필요합니다: pip install flask\n"
        "또는: pip install flask --break-system-packages"
    )

app = Flask(__name__)


# ---------------------------------------------------------------------------
# 응답 생성 로직
# ---------------------------------------------------------------------------

def _make_mock_content(messages: list) -> str:
    """
    요청 메시지를 분석해 judge 파서가 통과할 수 있는 더미 응답 생성.

    pairwise 판정 vs single grading을 user 메시지 내용으로 구분한다.
    실제 GPT-4 응답과 동일한 형식이어야 parse_pairwise_verdict,
    parse_single_score 함수가 올바르게 파싱된다.
    """
    last_user = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user = m.get("content", "")
            break

    # reference-guided pairwise (더 구체적인 조건을 먼저 체크)
    # build_pairwise_prompt(reference=...) 는 "Reference Answer"와 "Assistant A/B" 모두 포함
    if "Reference Answer" in last_user and "Assistant A" in last_user:
        return (
            "Comparing both responses with the reference answer, "
            "Assistant B's response more closely matches the reference in terms of accuracy.\n\n"
            "My final verdict is: [[B]]"
        )

    # generic pairwise: "Assistant A"와 "Assistant B" 둘 다 포함
    if "Assistant A" in last_user and "Assistant B" in last_user:
        return (
            "Both assistants provided relevant and helpful responses to the question. "
            "Assistant A's response was slightly more detailed and well-structured, "
            "covering the key points more comprehensively.\n\n"
            "My final verdict is: [[A]]"
        )

    # single grading (Figure 6 형식)
    return (
        "The response addresses the question with reasonable depth and clarity. "
        "The answer demonstrates good understanding of the topic and provides "
        "relevant information. Minor improvements could be made in structure.\n\n"
        "Rating: [[7]]"
    )


def _make_response_body(content: str, model: str) -> dict:
    """OpenAI Chat Completions API 응답 형식으로 래핑."""
    return {
        "id": f"chatcmpl-mock-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        },
    }


# ---------------------------------------------------------------------------
# API 엔드포인트
# ---------------------------------------------------------------------------

@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    """
    POST /v1/chat/completions — OpenAI Chat Completions API 호환 엔드포인트.

    실제 vLLM / OpenAI와 동일한 요청/응답 형식을 따른다.
    """
    data = request.get_json(force=True)
    messages = data.get("messages", [])
    model = data.get("model", "gpt-4-mock")

    content = _make_mock_content(messages)
    response_body = _make_response_body(content, model)

    app.logger.info(
        f"[mock] model={model}, "
        f"messages={len(messages)}, "
        f"response_len={len(content)}"
    )

    return jsonify(response_body)


@app.route("/v1/models", methods=["GET"])
def list_models():
    """GET /v1/models — 사용 가능한 모델 목록 반환."""
    return jsonify({
        "object": "list",
        "data": [
            {"id": "gpt-4-mock", "object": "model", "created": 0, "owned_by": "mock"},
            {"id": "gpt-4",      "object": "model", "created": 0, "owned_by": "mock"},
        ],
    })


@app.route("/health", methods=["GET"])
def health():
    """헬스체크 엔드포인트."""
    return jsonify({"status": "ok", "server": "mock_openai_server"})


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mock OpenAI-compatible API Server")
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9999)
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(f"Mock OpenAI Server running on http://{args.host}:{args.port}/v1")
    print("Endpoints:")
    print(f"  POST http://localhost:{args.port}/v1/chat/completions")
    print(f"  GET  http://localhost:{args.port}/v1/models")
    print(f"  GET  http://localhost:{args.port}/health")
    app.run(host=args.host, port=args.port, debug=args.debug)