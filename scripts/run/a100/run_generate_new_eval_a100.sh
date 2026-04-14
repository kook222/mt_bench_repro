#!/bin/bash
# scripts/run/a100/run_generate_new_eval_a100.sh
#
# Self-judge bias 증명을 위한 신규 eval 모델 2개 답변 생성.
#
# 추가 이유:
#   현재 eval 모델 7개 중 LLaMA eval = 1개, Qwen eval = 0개
#   → Qwen judge가 Qwen 모델을 유리하게 채점하는 symmetric bias를 보일 수 없음
#
# 신규 생성 모델 2개:
#   Llama-2-7b-chat    : LLaMA judge의 동일 모델 → 가장 강한 self-judge 케이스
#   Qwen2.5-7B-Instruct: Qwen judge의 동일 family → Qwen self-judge 케이스
#
# 최종 eval 모델 7개:
#   [LLaMA] Llama-2-7b-chat (신규), Llama-3.1-8B-Instruct (기존)
#   [Qwen]  Qwen2.5-7B-Instruct (신규)
#   [중립]  gemma-2-9b-it, Mistral-7B-Instruct-v0.3,
#           Phi-3.5-mini-Instruct, Zephyr-7B-beta (모두 기존)

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
VLLM_LOG="/tmp/vllm_generate_new_eval.log"
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

# 신규 생성 모델: "model_id:hf_id:max_len:gpu_util"
# Llama-3.1-8B-Instruct 답변은 Phase 3에 이미 존재 → 생성 불필요
# Qwen2.5-7B-Instruct 1개만 신규 생성
NEW_MODELS=(
  "Qwen2.5-7B-Instruct:Qwen/Qwen2.5-7B-Instruct:8192:0.88"
)

echo "=============================="
echo " 신규 eval 답변 생성"
echo " 대상: Llama-2-7b-chat, Qwen2.5-7B-Instruct"
echo " Date: $(date)"
echo "=============================="

for ENTRY in "${NEW_MODELS[@]}"; do
  MODEL_ID="${ENTRY%%:*}"; REST="${ENTRY#*:}"
  HF_ID="${REST%%:*}";     REST="${REST#*:}"
  MAX_LEN="${REST%%:*}";   GPU_UTIL="${REST##*:}"
  MODEL_DIR="$MODEL_BASE_DIR/$MODEL_ID"
  ANSWER_FILE="$ANSWERS_DIR/${MODEL_ID}.jsonl"

  echo ""
  echo "────────────────────────────────────────────"
  echo " $MODEL_ID"
  echo "────────────────────────────────────────────"

  if [ -f "$ANSWER_FILE" ]; then
    n=$(wc -l < "$ANSWER_FILE" | tr -d ' ')
    [ "$n" -ge 80 ] && echo "[SKIP] 완료 ($n lines)" && continue
  fi

  [ ! -d "$MODEL_DIR" ] && echo "[ERROR] 모델 없음: $MODEL_DIR" && exit 1

  vllm serve "$MODEL_DIR" \
    --served-model-name "$MODEL_ID" \
    --api-key EMPTY --port "$VLLM_PORT" \
    --max-model-len "$MAX_LEN" --dtype auto \
    --gpu-memory-utilization "$GPU_UTIL" \
    > "$VLLM_LOG" 2>&1 &
  VLLM_PID=$!

  WAITED=0
  until curl -s "http://localhost:$VLLM_PORT/health" > /dev/null 2>&1; do
    [ "$WAITED" -ge 300 ] && echo "[ERROR] 서버 시작 실패" && exit 1
    sleep 5; WAITED=$((WAITED + 5))
  done
  echo "[OK] 서버 준비 (${WAITED}s)"

  python3 -m mtbench_repro.cli generate \
    --questions "$QUESTIONS" --answers-dir "$ANSWERS_DIR" \
    --model-id "$MODEL_ID" --vllm-host localhost --vllm-port "$VLLM_PORT" \
    --temperature 0.7 --max-tokens 1024 --sleep 0.3

  cleanup_server
  echo "[OK] $MODEL_ID 완료"
done

echo ""
echo "다음: bash scripts/run/a100/run_judge_llama_a100.sh"
