#!/bin/bash
# scripts/run_judge_multi_a100.sh
#
# 여러 모델의 답변을 judge하고 집계한다.
# generate가 모두 완료된 후 실행.
#
# judge 모델은 JUDGE_MODEL_ID로 지정.
# - 로컬 vLLM judge: JUDGE_USE_VLLM=true (기본)
# - GPT-4o-mini judge: JUDGE_USE_VLLM=false + OPENAI_API_KEY 필요

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

export PYTHONPATH="$PROJECT_DIR/src"
export HOME="/tmp"
export LOGNAME="clink-seunghyun"
export USER="clink-seunghyun"
export PIP_CACHE_DIR="/tmp/pip_cache"
export HF_HOME="/tmp/hf_home"
export TORCHINDUCTOR_CACHE_DIR="/tmp/torchinductor_cache"
export TRITON_CACHE_DIR="/tmp/triton_cache"

HOME_DIR="/home/clink-seunghyun"
MODEL_BASE_DIR="$HOME_DIR/models"
QUESTIONS="$PROJECT_DIR/data/mt_bench_questions.jsonl"
ANSWERS_DIR="$PROJECT_DIR/data/answers/"
JUDGMENTS_DIR="$PROJECT_DIR/data/judgments/"
OUTPUT_CSV="$PROJECT_DIR/data/results_multi.csv"
VLLM_PORT=8000
VLLM_LOG="$HOME_DIR/vllm_judge.log"

# ── 경량 의존성 설치 (vllm/vllm-openai 이미지 전용) ──────────────────────
echo "[Init] 경량 의존성 설치..."
pip install openai tabulate tqdm --target /tmp/site-extra -q
export PYTHONPATH="/tmp/site-extra:$PROJECT_DIR/src"
echo "[Init] 완료."

# ── 설정 ──────────────────────────────────────────────────────────────────
# judge 모델 설정 (두 가지 중 하나 선택)
JUDGE_USE_VLLM="${JUDGE_USE_VLLM:-true}"          # true: 로컬 vLLM judge
JUDGE_MODEL_ID="${JUDGE_MODEL_ID:-Qwen2.5-14B-Instruct}"  # vLLM judge 모델
JUDGE_MODEL_DIR="$MODEL_BASE_DIR/$JUDGE_MODEL_ID"

# 평가할 모델 목록 (data/answers/ 에 파일이 있어야 함)
EVAL_MODELS=(
  "Qwen2.5-7B-Instruct"
  "Llama-3.1-8B-Instruct"
  "Mistral-7B-Instruct-v0.3"
)

echo "=============================="
echo " Multi-model Judge"
echo " judge: $JUDGE_MODEL_ID (vLLM=$JUDGE_USE_VLLM)"
echo " 평가 모델: ${EVAL_MODELS[*]}"
echo " Date: $(date)"
echo "=============================="

# ── Judge 클라이언트 설정 ──────────────────────────────────────────────────
if [ "$JUDGE_USE_VLLM" = "true" ]; then
  if [ ! -d "$JUDGE_MODEL_DIR" ]; then
    echo "[ERROR] judge 모델 없음: $JUDGE_MODEL_DIR"
    exit 1
  fi

  # judge vLLM 서버 시작
  python -m vllm.entrypoints.openai.api_server \
    --model "$JUDGE_MODEL_DIR" \
    --served-model-name "$JUDGE_MODEL_ID" \
    --api-key EMPTY \
    --port "$VLLM_PORT" \
    --max-model-len 4096 \
    --dtype auto \
    --gpu-memory-utilization 0.90 \
    > "$VLLM_LOG" 2>&1 &
  VLLM_PID=$!

  MAX_WAIT=300
  WAITED=0
  until curl -s "http://localhost:$VLLM_PORT/health" > /dev/null 2>&1; do
    if [ "$WAITED" -ge "$MAX_WAIT" ]; then
      echo "[ERROR] judge 서버 시작 실패"
      tail -20 "$VLLM_LOG"
      kill "$VLLM_PID" 2>/dev/null || true
      exit 1
    fi
    sleep 5; WAITED=$((WAITED + 5))
  done
  echo "[OK] judge 서버 준비 완료"

  BASE_URL="http://localhost:$VLLM_PORT/v1"
  API_KEY="EMPTY"
else
  # GPT-4o-mini judge
  if [ -z "$OPENAI_API_KEY" ]; then
    echo "[ERROR] OPENAI_API_KEY 환경변수가 없습니다."
    exit 1
  fi
  BASE_URL="https://api.openai.com/v1"
  API_KEY="$OPENAI_API_KEY"
  JUDGE_MODEL_ID="gpt-4o-mini"
  echo "[INFO] GPT-4o-mini judge 사용"
fi

# ── Step 1: Single-answer grading ─────────────────────────────────────────
echo ""
echo "[Step 1] Single-answer grading..."
for MODEL_ID in "${EVAL_MODELS[@]}"; do
  ANSWER_FILE="$ANSWERS_DIR/${MODEL_ID}.jsonl"
  if [ ! -f "$ANSWER_FILE" ]; then
    echo "[SKIP] 답변 파일 없음: $ANSWER_FILE"
    continue
  fi
  echo "  채점: $MODEL_ID"
  python -m mtbench_repro.cli judge-single \
    --questions "$QUESTIONS" \
    --answers-dir "$ANSWERS_DIR" \
    --output-dir "$JUDGMENTS_DIR" \
    --model-id "$MODEL_ID" \
    --judge-model "$JUDGE_MODEL_ID" \
    --openai-base-url "$BASE_URL" \
    --openai-api-key "$API_KEY" \
    --sleep 0.3
done

# ── Step 2: Pairwise comparison ────────────────────────────────────────────
echo ""
echo "[Step 2] Pairwise comparison (AB/BA swap)..."
for ((i=0; i<${#EVAL_MODELS[@]}; i++)); do
  for ((j=i+1; j<${#EVAL_MODELS[@]}; j++)); do
    MODEL_A="${EVAL_MODELS[$i]}"
    MODEL_B="${EVAL_MODELS[$j]}"
    A_FILE="$ANSWERS_DIR/${MODEL_A}.jsonl"
    B_FILE="$ANSWERS_DIR/${MODEL_B}.jsonl"
    if [ ! -f "$A_FILE" ] || [ ! -f "$B_FILE" ]; then
      echo "[SKIP] $MODEL_A vs $MODEL_B (답변 파일 없음)"
      continue
    fi
    echo "  비교: $MODEL_A vs $MODEL_B"
    python -m mtbench_repro.cli judge-pairwise \
      --questions "$QUESTIONS" \
      --answers-dir "$ANSWERS_DIR" \
      --output-dir "$JUDGMENTS_DIR" \
      --model-a "$MODEL_A" \
      --model-b "$MODEL_B" \
      --judge-model "$JUDGE_MODEL_ID" \
      --openai-base-url "$BASE_URL" \
      --openai-api-key "$API_KEY" \
      --sleep 0.5
  done
done

# ── Step 3: Reference-guided grading ──────────────────────────────────────
echo ""
echo "[Step 3] Reference-guided grading (math/reasoning/coding)..."
for MODEL_ID in "${EVAL_MODELS[@]}"; do
  ANSWER_FILE="$ANSWERS_DIR/${MODEL_ID}.jsonl"
  [ -f "$ANSWER_FILE" ] || continue
  echo "  reference 채점: $MODEL_ID"
  python -m mtbench_repro.cli judge-reference \
    --questions "$QUESTIONS" \
    --answers-dir "$ANSWERS_DIR" \
    --output-dir "$JUDGMENTS_DIR" \
    --mode single \
    --model-id "$MODEL_ID" \
    --judge-model "$JUDGE_MODEL_ID" \
    --openai-base-url "$BASE_URL" \
    --openai-api-key "$API_KEY" \
    --sleep 0.3
done

# ── Step 4: 집계 ──────────────────────────────────────────────────────────
echo ""
echo "[Step 4] 집계 및 추이 분석..."
python -m mtbench_repro.cli aggregate \
  --judgments-dir "$JUDGMENTS_DIR" \
  --output-csv "$OUTPUT_CSV"

# ── judge 서버 종료 ────────────────────────────────────────────────────────
if [ "$JUDGE_USE_VLLM" = "true" ] && [ -n "${VLLM_PID:-}" ]; then
  kill "$VLLM_PID" 2>/dev/null || true
  wait "$VLLM_PID" 2>/dev/null || true
  echo "[OK] judge 서버 종료"
fi

echo ""
echo "=============================="
echo " 전체 judge 완료"
echo " CSV: $OUTPUT_CSV"
echo " Date: $(date)"
echo "=============================="
