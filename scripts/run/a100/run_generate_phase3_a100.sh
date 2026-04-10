#!/bin/bash
# scripts/run/a100/run_generate_phase3_a100.sh
#
# Phase 3: Llama-3.1-8B-Instruct 답변 생성.
#
# Phase 3 eval 모델 구성 변경:
#   - Qwen2.5-7B-Instruct 제거 (Qwen2.5 judge와 동일 패밀리 → self-judge 편향)
#   - Llama-3.1-8B-Instruct 추가 (이종 아키텍처, 편향 없음)
#
# 나머지 6개 모델(SOLAR / gemma / Yi / Zephyr / Mistral / Phi)은
# Phase 2에서 생성된 data/answers/ 파일을 그대로 재사용한다.
# → Llama 1개 모델만 새로 생성하면 된다.
#
# 전제:
#   - meta-llama/Llama-3.1-8B-Instruct 모델이 MODEL_BASE_DIR에 다운로드되어 있어야 함.
#   - Phase 2 answers가 data/answers/ 에 있어야 함.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_DIR"

HOME_DIR="$(dirname "$PROJECT_DIR")"
export HOME="/tmp"
export LOGNAME="$(whoami)"
export USER="$(whoami)"
export PIP_CACHE_DIR="/tmp/pip_cache"
export HF_HOME="/tmp/hf_home"
export TORCHINDUCTOR_CACHE_DIR="/tmp/torchinductor_cache"
export TRITON_CACHE_DIR="/tmp/triton_cache"

MODEL_BASE_DIR="$HOME_DIR/models"
QUESTIONS="$PROJECT_DIR/data/mt_bench_questions.jsonl"
ANSWERS_DIR="$PROJECT_DIR/data/answers/"
VLLM_PORT=8000
VLLM_LOG="/tmp/vllm_generate_phase3.log"
VLLM_PID=""

cleanup_server() {
  if [ -n "${VLLM_PID:-}" ]; then
    kill "$VLLM_PID" 2>/dev/null || true
    wait "$VLLM_PID" 2>/dev/null || true
    VLLM_PID=""
  fi
}
trap cleanup_server EXIT INT TERM

# ── 경량 의존성 설치 (vllm/vllm-openai 이미지 전용) ──────────────────────
echo "[Init] 경량 의존성 설치..."
pip install openai tabulate tqdm --target /tmp/site-extra -q
export PYTHONPATH="/tmp/site-extra:$PROJECT_DIR/src"
echo "[Init] 완료."

# ── Phase 3 신규 모델 (1개만) ───────────────────────────────────────────────
MODEL_ID="Llama-3.1-8B-Instruct"
HF_ID="meta-llama/Llama-3.1-8B-Instruct"
MODEL_DIR="$MODEL_BASE_DIR/$MODEL_ID"

echo "=============================="
echo " Phase 3 Answer Generation"
echo " 신규 모델: $MODEL_ID"
echo " (나머지 6개 모델은 Phase 2 파일 재사용)"
echo " Date: $(date)"
echo "=============================="

# Phase 2 answers 존재 여부 확인 (참고용)
echo ""
echo "[Info] Phase 2 답변 파일 확인:"
for m in SOLAR-10.7B-Instruct gemma-2-9b-it Yi-1.5-9B-Chat Zephyr-7B-beta Mistral-7B-Instruct-v0.3 Phi-3.5-mini-Instruct; do
  if [ -f "$ANSWERS_DIR/${m}.jsonl" ]; then
    n=$(wc -l < "$ANSWERS_DIR/${m}.jsonl" | tr -d ' ')
    echo "  [OK] $m ($n lines)"
  else
    echo "  [WARN] $m 파일 없음 — Phase 2 먼저 실행 필요"
  fi
done
echo ""

# 모델 디렉토리 확인
if [ ! -d "$MODEL_DIR" ]; then
  echo "[ERROR] 모델 디렉토리 없음: $MODEL_DIR"
  echo "        먼저 다운로드:"
  echo "        export PATH=\"\$HOME/.local/bin:\$PATH\""
  echo "        hf download $HF_ID --local-dir $MODEL_DIR"
  exit 1
fi

# 이미 생성된 경우 resume 안내
ANSWER_FILE="$ANSWERS_DIR/${MODEL_ID}.jsonl"
if [ -f "$ANSWER_FILE" ]; then
  EXISTING=$(wc -l < "$ANSWER_FILE" | tr -d ' ')
  echo "[INFO] 기존 답변 파일 발견: $EXISTING 줄. resume 모드로 실행."
fi

# vLLM 서버 시작
echo "[Start] vLLM 서버 시작: $MODEL_ID"
vllm serve "$MODEL_DIR" \
  --served-model-name "$MODEL_ID" \
  --api-key EMPTY \
  --port "$VLLM_PORT" \
  --max-model-len 4096 \
  --dtype auto \
  --gpu-memory-utilization 0.90 \
  > "$VLLM_LOG" 2>&1 &
VLLM_PID=$!

# 서버 준비 대기 (최대 300초)
MAX_WAIT=300
WAITED=0
until curl -s "http://localhost:$VLLM_PORT/health" > /dev/null 2>&1; do
  if [ "$WAITED" -ge "$MAX_WAIT" ]; then
    echo "[ERROR] vLLM 서버가 ${MAX_WAIT}초 내에 시작되지 않음."
    tail -20 "$VLLM_LOG"
    kill "$VLLM_PID" 2>/dev/null || true
    exit 1
  fi
  sleep 5
  WAITED=$((WAITED + 5))
done
echo "[OK] 서버 준비 완료 (${WAITED}s)"

# 답변 생성
python3 -m mtbench_repro.cli generate \
  --questions "$QUESTIONS" \
  --answers-dir "$ANSWERS_DIR" \
  --model-id "$MODEL_ID" \
  --vllm-host localhost \
  --vllm-port "$VLLM_PORT" \
  --temperature 0.7 \
  --max-tokens 1024 \
  --sleep 0.3

echo "[OK] 생성 완료: $ANSWER_FILE"

# vLLM 서버 종료
cleanup_server
echo "[OK] 서버 종료"

echo ""
echo "=============================="
echo " Phase 3 답변 생성 완료"
echo " Phase 3 eval 모델 7개:"
for m in Llama-3.1-8B-Instruct SOLAR-10.7B-Instruct gemma-2-9b-it Yi-1.5-9B-Chat Zephyr-7B-beta Mistral-7B-Instruct-v0.3 Phi-3.5-mini-Instruct; do
  if [ -f "$ANSWERS_DIR/${m}.jsonl" ]; then
    n=$(wc -l < "$ANSWERS_DIR/${m}.jsonl" | tr -d ' ')
    echo "  [OK] $m ($n lines)"
  else
    echo "  [MISS] $m"
  fi
done
echo " 다음 단계: bash scripts/run/a100/run_judge_phase3_a100.sh"
echo " Date: $(date)"
echo "=============================="
