#!/bin/bash
# scripts/run_judge_unseen_vllm_a100.sh
#
# 단일 vLLM judge(Qwen32/InternLM20 등)를 unseen 모델 answers에 대해 실행한다.
# full-80과 TopDisc subset 모두 QUESTIONS/ANSWERS_DIR/OUTPUT_DIR override로 재사용 가능.
#
# 예시:
#   JUDGE_MODEL_ID=Qwen2.5-32B-Instruct QUANTIZATION=awq GPU_MEMORY_UTILIZATION=0.95 \
#   MAX_MODEL_LEN=2048 ENFORCE_EAGER=true MAX_NUM_SEQS=1 \
#   bash scripts/run_judge_unseen_vllm_a100.sh
#
#   JUDGE_MODEL_ID=internlm2_5-20b-chat TRUST_REMOTE_CODE=true GPU_MEMORY_UTILIZATION=0.92 \
#   bash scripts/run_judge_unseen_vllm_a100.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
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
VLLM_LOG="/tmp/vllm_judge_unseen.log"

JUDGE_MODEL_ID="${JUDGE_MODEL_ID:-Qwen2.5-32B-Instruct}"
JUDGE_MODEL_DIR="${JUDGE_MODEL_DIR:-$MODEL_BASE_DIR/$JUDGE_MODEL_ID}"
JUDGE_LABEL="${JUDGE_LABEL:-$(echo "$JUDGE_MODEL_ID" | tr '[:upper:]' '[:lower:]' | tr './' '__' | tr '-' '_')}"
OUTPUT_DIR="${OUTPUT_DIR:-$PROJECT_DIR/data/judgments_unseen/$JUDGE_LABEL}"
OUTPUT_CSV="${OUTPUT_CSV:-$PROJECT_DIR/data/results_unseen_${JUDGE_LABEL}.csv}"

QUANTIZATION="${QUANTIZATION:-none}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-8192}"
TRUST_REMOTE_CODE="${TRUST_REMOTE_CODE:-false}"
ENFORCE_EAGER="${ENFORCE_EAGER:-false}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-}"

RUN_SINGLE="${RUN_SINGLE:-true}"
RUN_PAIRWISE="${RUN_PAIRWISE:-true}"
RUN_REFERENCE="${RUN_REFERENCE:-true}"
RUN_AGGREGATE="${RUN_AGGREGATE:-true}"

DEFAULT_MODELS=(
  "EXAONE-3.5-7.8B-Instruct"
  "granite-3.1-8b-instruct"
  "Falcon3-7B-Instruct"
  "bloomz-7b1-mt"
)

if [ "$#" -gt 0 ]; then
  EVAL_MODELS=("$@")
else
  EVAL_MODELS=("${DEFAULT_MODELS[@]}")
fi

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

echo "=============================="
echo " Unseen vLLM Judge"
echo " Judge: $JUDGE_MODEL_ID"
echo " Questions: $QUESTIONS"
echo " Answers dir: $ANSWERS_DIR"
echo " Output dir: $OUTPUT_DIR"
echo " Models: ${EVAL_MODELS[*]}"
echo " Date: $(date)"
echo "=============================="

if [ ! -d "$JUDGE_MODEL_DIR" ]; then
  echo "[ERROR] judge 모델 디렉토리 없음: $JUDGE_MODEL_DIR"
  exit 1
fi

for MODEL_ID in "${EVAL_MODELS[@]}"; do
  if [ ! -f "$ANSWERS_DIR/${MODEL_ID}.jsonl" ]; then
    echo "[ERROR] 답변 파일 없음: $ANSWERS_DIR/${MODEL_ID}.jsonl"
    exit 1
  fi
done

SERVE_ARGS=(
  "$JUDGE_MODEL_DIR"
  --served-model-name "$JUDGE_MODEL_ID"
  --api-key EMPTY
  --port "$VLLM_PORT"
  --max-model-len "$MAX_MODEL_LEN"
  --dtype auto
  --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION"
)

if [ "$QUANTIZATION" != "none" ]; then
  SERVE_ARGS+=(--quantization "$QUANTIZATION")
fi
if [ "$TRUST_REMOTE_CODE" = "true" ]; then
  SERVE_ARGS+=(--trust-remote-code)
fi
if [ "$ENFORCE_EAGER" = "true" ]; then
  SERVE_ARGS+=(--enforce-eager)
fi
if [ -n "$MAX_NUM_SEQS" ]; then
  SERVE_ARGS+=(--max-num-seqs "$MAX_NUM_SEQS")
fi

PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
vllm serve "${SERVE_ARGS[@]}" > "$VLLM_LOG" 2>&1 &
VLLM_PID=$!

MAX_WAIT=600
WAITED=0
until curl -s "http://localhost:$VLLM_PORT/health" > /dev/null 2>&1; do
  if [ "$WAITED" -ge "$MAX_WAIT" ]; then
    echo "[ERROR] judge 서버가 ${MAX_WAIT}초 내에 시작되지 않음."
    tail -20 "$VLLM_LOG"
    exit 1
  fi
  sleep 5
  WAITED=$((WAITED + 5))
done
echo "[OK] judge 서버 준비 완료 (${WAITED}s)"

BASE_URL="http://localhost:$VLLM_PORT/v1"

if [ "$RUN_SINGLE" = "true" ]; then
  echo ""
  echo "[Step 1] Single-answer grading"
  for MODEL_ID in "${EVAL_MODELS[@]}"; do
    echo "  - $MODEL_ID"
    python3 -m mtbench_repro.cli judge-single \
      --questions "$QUESTIONS" \
      --answers-dir "$ANSWERS_DIR" \
      --output-dir "$OUTPUT_DIR" \
      --model-id "$MODEL_ID" \
      --judge-model "$JUDGE_MODEL_ID" \
      --provider openai_compatible \
      --api-key EMPTY \
      --base-url "$BASE_URL" \
      --sleep 0.3
  done
fi

if [ "$RUN_PAIRWISE" = "true" ]; then
  echo ""
  echo "[Step 2] Pairwise comparison"
  for ((i=0; i<${#EVAL_MODELS[@]}; i++)); do
    for ((j=i+1; j<${#EVAL_MODELS[@]}; j++)); do
      MODEL_A="${EVAL_MODELS[$i]}"
      MODEL_B="${EVAL_MODELS[$j]}"
      echo "  - $MODEL_A vs $MODEL_B"
      python3 -m mtbench_repro.cli judge-pairwise \
        --questions "$QUESTIONS" \
        --answers-dir "$ANSWERS_DIR" \
        --output-dir "$OUTPUT_DIR" \
        --model-a "$MODEL_A" \
        --model-b "$MODEL_B" \
        --judge-model "$JUDGE_MODEL_ID" \
        --provider openai_compatible \
        --api-key EMPTY \
        --base-url "$BASE_URL" \
        --sleep 0.5
    done
  done
fi

if [ "$RUN_REFERENCE" = "true" ]; then
  echo ""
  echo "[Step 3] Reference-guided grading"
  for MODEL_ID in "${EVAL_MODELS[@]}"; do
    echo "  - $MODEL_ID"
    python3 -m mtbench_repro.cli judge-reference \
      --questions "$QUESTIONS" \
      --answers-dir "$ANSWERS_DIR" \
      --output-dir "$OUTPUT_DIR" \
      --mode single \
      --model-id "$MODEL_ID" \
      --judge-model "$JUDGE_MODEL_ID" \
      --provider openai_compatible \
      --api-key EMPTY \
      --base-url "$BASE_URL" \
      --sleep 0.3
  done
fi

if [ "$RUN_AGGREGATE" = "true" ]; then
  echo ""
  echo "[Step 4] Aggregate"
  python3 -m mtbench_repro.cli aggregate \
    --judgments-dir "$OUTPUT_DIR" \
    --questions-path "$QUESTIONS" \
    --output-csv "$OUTPUT_CSV"
fi

echo ""
echo "=============================="
echo " Unseen judge complete"
echo " Output dir: $OUTPUT_DIR"
echo " Output csv: $OUTPUT_CSV"
echo "=============================="
