#!/bin/bash
# scripts/run/a100/run_judge_gemma2_27b_ko_rerun.sh
#
# ko Gemma2-27B-AWQ judge 단독 재실행.
# 기존 run_judge_gemma2_ko_a100.sh에서 27B가 미완료(Llama만 존재).
# 2B/9B는 완료됐으므로 27B만 실행.
#
# 출력:
#   data/ko/judgments/gemma2/judge_gemma2_27B/
#   data/ko/results/results_ko_judge_gemma2_27B.csv

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
JUDGE_MODEL_ID="gemma-2-27b-it"
JUDGE_MODEL_DIR="$MODEL_BASE_DIR/$JUDGE_MODEL_ID"
QUESTIONS="$PROJECT_DIR/data/ko/questions.jsonl"
ANSWERS_DIR="$PROJECT_DIR/data/ko/answers/"
JUDGMENTS_DIR="$PROJECT_DIR/data/ko/judgments/gemma2/judge_gemma2_27B"
KO_RESULTS_DIR="$PROJECT_DIR/data/ko/results"
VLLM_PORT=8000
VLLM_LOG="/tmp/vllm_judge_gemma2_27b_ko.log"
VLLM_PID=""
GEMMA2_TEMPLATE="$SCRIPT_DIR/gemma2_chat_template.jinja"

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

if [ ! -f "$QUESTIONS" ]; then
  echo "[ERROR] 한국어 질문 파일 없음: $QUESTIONS"
  exit 1
fi

if [ ! -d "$JUDGE_MODEL_DIR" ]; then
  echo "[ERROR] judge 모델 없음: $JUDGE_MODEL_DIR"
  echo "        huggingface-cli download google/gemma-2-27b-it-AWQ --local-dir $JUDGE_MODEL_DIR"
  exit 1
fi

mkdir -p "$JUDGMENTS_DIR" "$KO_RESULTS_DIR"

EVAL_MODELS=(
  "Llama-3.1-8B-Instruct"
  "EEVE-Korean-Instruct-10.8B"
  "EXAONE-3.5-7.8B-Instruct"
  "gemma-2-9b-it"
  "Mistral-7B-Instruct-v0.3"
  "Phi-3.5-mini-Instruct"
)

echo "=============================="
echo " ko Gemma2-27B-AWQ Judge 재실행"
echo " Date: $(date)"
echo "=============================="

# vLLM 서버 시작 (AWQ, float16)
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
vllm serve "$JUDGE_MODEL_DIR" \
  --served-model-name "$JUDGE_MODEL_ID" \
  --api-key EMPTY \
  --port "$VLLM_PORT" \
  --max-model-len 8192 \
  --dtype float16 \
  --quantization awq \
  --gpu-memory-utilization 0.95 \
  --enforce-eager \
  --max-num-seqs 1 \
  --chat-template "$GEMMA2_TEMPLATE" \
  > "$VLLM_LOG" 2>&1 &
VLLM_PID=$!

MAX_WAIT=600
WAITED=0
until curl -s "http://localhost:$VLLM_PORT/health" > /dev/null 2>&1; do
  if [ "$WAITED" -ge "$MAX_WAIT" ]; then
    echo "[ERROR] 서버 ${MAX_WAIT}초 내 미시작."
    tail -20 "$VLLM_LOG"
    exit 1
  fi
  sleep 5; WAITED=$((WAITED + 5))
done
echo "[OK] 서버 준비 완료 (${WAITED}s)"

BASE_URL="http://localhost:$VLLM_PORT/v1"
API_KEY="EMPTY"

# Step 1: Single-answer grading
echo ""
echo "[Step 1] Single-answer grading (--lang ko)..."
for MODEL_ID in "${EVAL_MODELS[@]}"; do
  echo "  채점: $MODEL_ID"
  python3 -m mtbench_repro.cli judge-single \
    --questions "$QUESTIONS" \
    --answers-dir "$ANSWERS_DIR" \
    --output-dir "$JUDGMENTS_DIR" \
    --model-id "$MODEL_ID" \
    --judge-model "$JUDGE_MODEL_ID" \
    --openai-base-url "$BASE_URL" \
    --openai-api-key "$API_KEY" \
    --lang ko \
    --sleep 0.3
done

# Step 2: Pairwise comparison
echo ""
echo "[Step 2] Pairwise comparison AB/BA (--lang ko)..."
for ((i=0; i<${#EVAL_MODELS[@]}; i++)); do
  for ((j=i+1; j<${#EVAL_MODELS[@]}; j++)); do
    MODEL_A="${EVAL_MODELS[$i]}"
    MODEL_B="${EVAL_MODELS[$j]}"
    echo "  비교: $MODEL_A vs $MODEL_B"
    python3 -m mtbench_repro.cli judge-pairwise \
      --questions "$QUESTIONS" \
      --answers-dir "$ANSWERS_DIR" \
      --output-dir "$JUDGMENTS_DIR" \
      --model-a "$MODEL_A" \
      --model-b "$MODEL_B" \
      --judge-model "$JUDGE_MODEL_ID" \
      --openai-base-url "$BASE_URL" \
      --openai-api-key "$API_KEY" \
      --lang ko \
      --sleep 0.5
  done
done

# Step 3: Reference-guided grading
echo ""
echo "[Step 3] Reference-guided grading (--lang ko)..."
for MODEL_ID in "${EVAL_MODELS[@]}"; do
  echo "  reference 채점: $MODEL_ID"
  python3 -m mtbench_repro.cli judge-reference \
    --questions "$QUESTIONS" \
    --answers-dir "$ANSWERS_DIR" \
    --output-dir "$JUDGMENTS_DIR" \
    --mode single \
    --model-id "$MODEL_ID" \
    --judge-model "$JUDGE_MODEL_ID" \
    --openai-base-url "$BASE_URL" \
    --openai-api-key "$API_KEY" \
    --lang ko \
    --sleep 0.3
done

# Step 4: 집계
echo ""
echo "[Step 4] 집계..."
python3 -m mtbench_repro.cli aggregate \
  --judgments-dir "$JUDGMENTS_DIR" \
  --questions-path "$QUESTIONS" \
  --output-csv "$KO_RESULTS_DIR/results_ko_judge_gemma2_27B.csv" \
  --output-ref-csv "$KO_RESULTS_DIR/results_ko_judge_gemma2_27B_reference.csv"
echo "[OK] CSV: $KO_RESULTS_DIR/results_ko_judge_gemma2_27B.csv"

cleanup_server

echo ""
echo "=============================="
echo " ko Gemma2-27B Judge 완료"
echo " Date: $(date)"
echo "=============================="
