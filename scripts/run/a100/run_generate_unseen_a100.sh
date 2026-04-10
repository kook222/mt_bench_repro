#!/bin/bash
# scripts/run/a100/run_generate_unseen_a100.sh
#
# unseen 모델 4개의 full-80 또는 subset answers를 A100에서 순차 생성한다.
# 사용 예:
#   bash scripts/run/a100/run_generate_unseen_a100.sh
#   QUESTIONS=data/mt_bench_questions_topdisc40.jsonl ANSWERS_DIR=data/answers_topdisc40 bash scripts/run/a100/run_generate_unseen_a100.sh

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

MODEL_BASE_DIR="${MODEL_BASE_DIR:-$HOME_DIR/models}"
QUESTIONS="${QUESTIONS:-$PROJECT_DIR/data/mt_bench_questions.jsonl}"
ANSWERS_DIR="${ANSWERS_DIR:-$PROJECT_DIR/data/answers_unseen}"
VLLM_PORT="${VLLM_PORT:-8000}"
VLLM_LOG="/tmp/vllm_generate_unseen.log"

VLLM_PID=""
cleanup_server() {
  if [ -n "${VLLM_PID:-}" ]; then
    kill "$VLLM_PID" 2>/dev/null || true
    wait "$VLLM_PID" 2>/dev/null || true
    VLLM_PID=""
  fi
}
trap cleanup_server EXIT INT TERM

echo "[Init] 경량 의존성 설치..."
pip install openai tabulate tqdm --target /tmp/site-extra -q
export PYTHONPATH="/tmp/site-extra:$PROJECT_DIR/src"
echo "[Init] 완료."

# 형식: HF_ID:MODEL_ID:GPU_UTIL:TRUST_REMOTE_CODE:MAX_MODEL_LEN
MODEL_LIST=(
  "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct:EXAONE-3.5-7.8B-Instruct:0.92:true:4096"
  "ibm-granite/granite-3.1-8b-instruct:granite-3.1-8b-instruct:0.90:false:4096"
  "tiiuae/Falcon3-7B-Instruct:Falcon3-7B-Instruct:0.90:false:4096"
  "allenai/OLMo-2-1124-7B-Instruct:OLMo-2-1124-7B-Instruct:0.90:false:4096"
)

echo "=============================="
echo " Unseen-model Generation"
echo " Questions: $QUESTIONS"
echo " Answers dir: $ANSWERS_DIR"
echo " Date: $(date)"
echo "=============================="

mkdir -p "$ANSWERS_DIR"

for ENTRY in "${MODEL_LIST[@]}"; do
  HF_ID="${ENTRY%%:*}"
  REST="${ENTRY#*:}"
  MODEL_ID="${REST%%:*}"
  REST="${REST#*:}"
  GPU_UTIL="${REST%%:*}"
  REST="${REST#*:}"
  TRUST_REMOTE_CODE="${REST%%:*}"
  MAX_MODEL_LEN="${REST##*:}"
  MODEL_DIR="$MODEL_BASE_DIR/$MODEL_ID"

  echo ""
  echo "──────────────────────────────"
  echo " 모델: $MODEL_ID"
  echo "──────────────────────────────"

  if [ ! -d "$MODEL_DIR" ]; then
    echo "[SKIP] 모델 디렉토리 없음: $MODEL_DIR"
    echo "       다운로드: hf download $HF_ID --local-dir $MODEL_DIR"
    continue
  fi

  ANSWER_FILE="$ANSWERS_DIR/${MODEL_ID}.jsonl"
  if [ -f "$ANSWER_FILE" ]; then
    EXISTING=$(wc -l < "$ANSWER_FILE" | tr -d ' ')
    echo "[INFO] 기존 답변 파일 발견: $EXISTING 줄. resume 모드로 실행."
  fi

  cleanup_server
  SERVE_ARGS=(
    "$MODEL_DIR"
    --served-model-name "$MODEL_ID"
    --api-key EMPTY
    --port "$VLLM_PORT"
    --max-model-len "$MAX_MODEL_LEN"
    --dtype auto
    --gpu-memory-utilization "$GPU_UTIL"
  )
  if [ "$TRUST_REMOTE_CODE" = "true" ]; then
    SERVE_ARGS+=(--trust-remote-code)
  fi

  vllm serve "${SERVE_ARGS[@]}" > "$VLLM_LOG" 2>&1 &
  VLLM_PID=$!

  MAX_WAIT=300
  WAITED=0
  until curl -s "http://localhost:$VLLM_PORT/health" > /dev/null 2>&1; do
    if [ "$WAITED" -ge "$MAX_WAIT" ]; then
      echo "[ERROR] vLLM 서버가 ${MAX_WAIT}초 내에 시작되지 않음."
      tail -20 "$VLLM_LOG"
      exit 1
    fi
    sleep 5
    WAITED=$((WAITED + 5))
  done
  echo "[OK] 서버 준비 완료 (${WAITED}s)"

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
  cleanup_server
done

echo ""
echo "=============================="
echo " Unseen 생성 완료"
ls -lh "$ANSWERS_DIR"/*.jsonl 2>/dev/null || echo " (없음)"
echo "=============================="
