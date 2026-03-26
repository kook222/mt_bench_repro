# src/client.py
"""
OpenAI-compatible ChatClient 구현.

왜 별도 파일로 분리하는가:
- judge_*.py와 generate.py가 모두 LLM API를 호출하므로
  retry, timeout, mock 등의 로직을 한 곳에서 관리한다.
- vLLM은 OpenAI-compatible endpoint를 제공하므로
  base_url만 바꾸면 OpenAI API와 vLLM을 동일 코드로 쓸 수 있다.
  로컬 mock(A100 없이 테스트)도 동일 인터페이스로 제공한다.

사용 방법:
    # OpenAI API 사용 시
    client = ChatClient(api_key="sk-...", base_url="https://api.openai.com/v1")

    # A100의 vLLM 서버 사용 시 (--served-model-name 옵션으로 모델명 설정)
    client = ChatClient(api_key="EMPTY", base_url="http://localhost:8000/v1")

    # 로컬 mock 테스트 시
    client = ChatClient.mock()
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ChatClient:
    """
    OpenAI Chat Completions API 호환 클라이언트.

    vLLM을 A100에서 --api-key EMPTY --served-model-name <name> 옵션으로
    실행하면 이 클라이언트를 그대로 사용할 수 있다.

    Attributes:
        api_key: API 키 (vLLM은 "EMPTY" 사용)
        base_url: API 엔드포인트 (OpenAI: "https://api.openai.com/v1",
                  vLLM: "http://localhost:8000/v1")
        default_model: 기본 모델명
        timeout: 요청 타임아웃 (초)
        max_retries: 실패 시 최대 재시도 횟수
        retry_delay: 재시도 간 대기 시간 (초)
        _mock: mock 모드 여부 (API 호출 없이 더미 응답 반환)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.openai.com/v1",
        default_model: str = "gpt-4",
        timeout: float = 120.0,
        max_retries: int = 3,
        retry_delay: float = 5.0,
        _mock: bool = False,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "EMPTY")
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._mock = _mock

        # openai 패키지를 선택적 임포트:
        # mock 모드에서는 패키지가 없어도 동작하게 해서
        # A100 환경 없는 로컬 개발을 가능하게 한다.
        if not _mock:
            try:
                import openai  # type: ignore
                self._client = openai.OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                    timeout=self.timeout,
                )
            except ImportError:
                raise ImportError(
                    "openai 패키지가 필요합니다: pip install openai\n"
                    "mock 모드로 쓰려면 ChatClient.mock()을 사용하세요."
                )

    @classmethod
    def mock(cls) -> "ChatClient":
        """
        API 호출 없이 더미 응답을 반환하는 mock 클라이언트 생성.

        로컬에서 파이프라인 흐름 검증 시 사용.
        mock 응답은 judge 파싱 함수가 통과할 수 있는 형식으로 반환된다.
        """
        return cls(_mock=True)

    @classmethod
    def from_vllm(
        cls,
        host: str = "localhost",
        port: int = 8000,
        model: str = "vicuna-13b",
        **kwargs: Any,
    ) -> "ChatClient":
        """
        A100에서 실행 중인 vLLM 서버에 연결하는 클라이언트 생성.

        vLLM 실행 명령 예시 (A100 서버):
            vllm serve $HOME/models/Qwen2.5-7B-Instruct \\
                --served-model-name Qwen2.5-7B-Instruct \\
                --api-key EMPTY \\
                --port 8000

        Args:
            host: vLLM 서버 호스트
            port: vLLM 서버 포트
            model: served-model-name으로 지정한 모델명
        """
        return cls(
            api_key="EMPTY",
            base_url=f"http://{host}:{port}/v1",
            default_model=model,
            **kwargs,
        )

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> str:
        """
        Chat Completions API를 호출하고 assistant 메시지 텍스트를 반환.

        temperature=0.0인 이유:
        - 논문에서 judge는 결정론적 판정을 위해 greedy decoding을 사용한다.
          (Section 4.1 "we use GPT-4 as judge")
        - 생성 시에는 호출 측에서 temperature를 명시적으로 변경해야 한다.

        retry 로직:
        - 네트워크 오류나 rate limit(429)은 retry_delay 후 재시도.
        - max_retries 초과 시 빈 문자열 반환 + 경고 로그.
          파이프라인을 멈추지 않고 해당 항목만 실패 처리하기 위함.

        Args:
            messages: [{"role": "system", "content": ...}, {"role": "user", ...}]
            model: 사용할 모델명 (None이면 default_model 사용)
            temperature: 생성 온도
            max_tokens: 최대 생성 토큰
            **kwargs: openai API에 전달할 추가 파라미터

        Returns:
            assistant 응답 텍스트. 실패 시 빈 문자열.
        """
        if self._mock:
            return self._mock_response(messages)

        model = model or self.default_model

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                return response.choices[0].message.content or ""

            except Exception as e:
                error_str = str(e)
                logger.warning(
                    f"API call failed (attempt {attempt}/{self.max_retries}): {error_str}"
                )
                if attempt < self.max_retries:
                    # rate limit(429)이면 더 오래 대기
                    delay = self.retry_delay * (2 if "429" in error_str else 1)
                    logger.info(f"Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"All {self.max_retries} attempts failed. Returning empty string.")

        return ""

    def _mock_response(self, messages: List[Dict[str, str]]) -> str:
        """
        파이프라인 검증용 더미 응답 생성.

        judge 파싱 함수가 통과할 수 있는 형식을 반환:
        - single grading: "Rating: [[7]]" 형식
        - pairwise: "[[A]]" 형식
        last user message 내용으로 어떤 judge 타입인지 판별한다.
        """
        last_user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user = m.get("content", "")
                break

        # pairwise judge 응답 mock: tie([[C]])를 반환
        # [[A]]를 항상 반환하면 AB/BA swap에서 항상 "inconsistent"가 되어
        # win rate가 전부 NaN이 된다. [[C]](tie)를 반환하면 AB·BA 모두 tie →
        # resolve_pairwise_winner → "tie" → win rate 0.5로 집계 가능.
        if "Assistant A" in last_user and "Assistant B" in last_user:
            return (
                "Both assistants provided responses of similar quality. "
                "It is difficult to determine a clear winner.\n"
                "My final verdict is: [[C]]"
            )

        # single grading 응답 mock: "Rating: [[rating]]" 형식
        # 논문 Figure 6의 파싱 패턴과 일치해야 한다
        return (
            "The response is helpful and addresses the question well. "
            "It covers the main points with sufficient detail.\n"
            "Rating: [[7]]"
        )

    def get_model_list(self) -> List[str]:
        """
        사용 가능한 모델 목록 조회 (vLLM 서버 상태 확인용).

        vLLM에서 GET /v1/models 엔드포인트를 통해 로드된 모델 확인.

        Returns:
            모델 ID 리스트. mock 모드면 빈 리스트.
        """
        if self._mock:
            return ["mock-model"]

        try:
            models = self._client.models.list()
            return [m.id for m in models.data]
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []