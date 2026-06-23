#!/bin/bash
# scripts/run/a100/run_judge_gemma2_ko_a100.sh
#
# 한국어 MT-Bench — Gemma 2 패밀리(2B / 9B / 27B) judge 실행.
#
# Qwen 실험(run_judge_ko_a100.sh)과 동일한 eval 모델 5개 사용.
# judge 프롬프트: 한국어 (--lang ko)
#
# ⚠️  Self-judge 주의:
#     gemma-2-9b-it은 eval 모델이기도 함.
#     single grading 시 자신의 답변을 자신이 채점하는 상황 발생.
#     → 분석 시 gemma-2-9b judge의 gemma-2-9b eval 결과는 별도 표기 권장.
#
# Judge 모델:
#   gemma-2-2b-it  : google/gemma-2-2b-it         (no quant)
#   gemma-2-9b-it  : google/gemma-2-9b-it          (no quant)
#   gemma-2-27b-it : google/gemma-2-27b-it-AWQ     (AWQ 4-bit)
#
# 출력:
#   data/ko/judgments/gemma2/judge_gemma2_{2B,9B,27B}/
#   data/ko/results/results_ko_gemma2_judge_{2B,9B,27B}.csv

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
QUESTIONS="$PROJECT_DIR/data/ko/questions.jsonl"
ANSWERS_DIR="$PROJECT_DIR/data/ko/answers/"
GEMMA2_JUDGE_DIR="$PROJECT_DIR/data/ko/judgments/gemma2"
KO_RESULTS_DIR="$PROJECT_DIR/data/ko/results"
VLLM_PORT=8000
VLLM_LOG="/tmp/vllm_judge_gemma2_ko.log"
VLLM_PID=""

cleanup_server() {
  if [ -n "${VLLM_PID:-}" ]; then
    kill "$VLLM_PID" 2>/dev/null || true
    wait "$VLLM_PID" 2>/dev/null || true
    VLLM_PID=""
  fi
}
trap cleanup_server EXIT INT TERM

# ── 경량 의존성 설치 ──────────────────────────────────────────────────────────
echo "[Init] 경량 의존성 설치..."
pip install openai tabulate tqdm --target /tmp/site-extra -q
export PYTHONPATH="/tmp/site-extra:$PROJECT_DIR/src"
echo "[Init] 완료."

# ── 질문 파일 확인 ────────────────────────────────────────────────────────────
if [ ! -f "$QUESTIONS" ]; then
  echo "[ERROR] 한국어 질문 파일 없음: $QUESTIONS"
  echo "        run_generate_ko_a100.sh를 먼저 실행하세요."
  exit 1
fi

# ── 출력 디렉토리 생성 ────────────────────────────────────────────────────────
mkdir -p "$GEMMA2_JUDGE_DIR" "$KO_RESULTS_DIR"

# ── eval 모델 목록 ────────────────────────────────────────────────────────────
EVAL_MODELS=(
  "Llama-3.1-8B-Instruct"
  "SOLAR-10.7B-Instruct"
  "gemma-2-9b-it"
  "Mistral-7B-Instruct-v0.3"
  "Phi-3.5-mini-Instruct"
)

# ── judge 라인업 ─────────────────────────────────────────────────────────────
# 형식: "judge_label:model_dir_name:quantization_flag:gpu_util"
JUDGE_LIST=(
  "judge_gemma2_2B:gemma-2-2b-it:none:0.70"
  "judge_gemma2_9B:gemma-2-9b-it:none:0.90"
  "judge_gemma2_27B:gemma-2-27b-it:awq:0.95"
)

echo "=============================="
echo " 한국어 MT-Bench — Gemma 2 Judge"
echo " eval 모델 5개: ${EVAL_MODELS[*]}"
echo " judge 3종: 2B / 9B / 27B-AWQ (한국어 프롬프트 --lang ko)"
echo " Date: $(date)"
echo "=============================="

# ── 답변 파일 사전 확인 ───────────────────────────────────────────────────────
echo ""
echo "[Check] eval 모델 한국어 답변 파일 확인:"
MISSING=0
for MODEL_ID in "${EVAL_MODELS[@]}"; do
  if [ -f "$ANSWERS_DIR/${MODEL_ID}.jsonl" ]; then
    n=$(wc -l < "$ANSWERS_DIR/${MODEL_ID}.jsonl" | tr -d ' ')
    echo "  [OK] $MODEL_ID ($n lines)"
  else
    echo "  [ERROR] $MODEL_ID 답변 없음: $ANSWERS_DIR/${MODEL_ID}.jsonl"
    MISSING=$((MISSING + 1))
  fi
done
if [ "$MISSING" -gt 0 ]; then
  echo "[ERROR] $MISSING개 모델 답변 파일 없음."
  echo "        먼저 bash scripts/run/a100/run_generate_ko_a100.sh 실행."
  exit 1
fi

# ============================================================================
# judge 루프: 3종 순차 실행
# ============================================================================
for JUDGE_ENTRY in "${JUDGE_LIST[@]}"; do
  JUDGE_LABEL="${JUDGE_ENTRY%%:*}"
  REST="${JUDGE_ENTRY#*:}"
  JUDGE_MODEL_ID="${REST%%:*}"
  REST="${REST#*:}"
  QUANT="${REST%%:*}"
  GPU_UTIL="${REST##*:}"

  JUDGE_MODEL_DIR="$MODEL_BASE_DIR/$JUDGE_MODEL_ID"
  JUDGMENTS_DIR="$GEMMA2_JUDGE_DIR/$JUDGE_LABEL"
  OUTPUT_CSV="$KO_RESULTS_DIR/results_ko_${JUDGE_LABEL}.csv"
  OUTPUT_REF_CSV="$KO_RESULTS_DIR/results_ko_${JUDGE_LABEL}_reference.csv"

  mkdir -p "$JUDGMENTS_DIR"

  echo ""
  echo "────────────────────────────────────────────"
  echo " Judge: $JUDGE_MODEL_ID ($JUDGE_LABEL)"
  echo " 양자화: $QUANT | GPU util: $GPU_UTIL"
  echo " 출력: $JUDGMENTS_DIR"
  echo " 프롬프트 언어: 한국어 (--lang ko)"
  echo "────────────────────────────────────────────"

  # 모델 디렉토리 확인
  if [ ! -d "$JUDGE_MODEL_DIR" ]; then
    echo "[ERROR] judge 모델 없음: $JUDGE_MODEL_DIR"
    if [ "$QUANT" = "awq" ]; then
      echo "        huggingface-cli download google/gemma-2-27b-it-AWQ --local-dir $JUDGE_MODEL_DIR"
    else
      echo "        huggingface-cli download google/${JUDGE_MODEL_ID} --local-dir $JUDGE_MODEL_DIR"
    fi
    exit 1
  fi

  # vLLM 서버 시작
  if [ "$QUANT" = "awq" ]; then
    PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
    vllm serve "$JUDGE_MODEL_DIR" \
      --served-model-name "$JUDGE_MODEL_ID" \
      --api-key EMPTY \
      --port "$VLLM_PORT" \
      --max-model-len 4096 \
      --dtype auto \
      --quantization awq \
      --gpu-memory-utilization "$GPU_UTIL" \
      --enforce-eager \
      --max-num-seqs 1 \
      > "$VLLM_LOG" 2>&1 &
  else
    vllm serve "$JUDGE_MODEL_DIR" \
      --served-model-name "$JUDGE_MODEL_ID" \
      --api-key EMPTY \
      --port "$VLLM_PORT" \
      --max-model-len 8192 \
      --dtype bfloat16 \
      --gpu-memory-utilization "$GPU_UTIL" \
      > "$VLLM_LOG" 2>&1 &
  fi
  VLLM_PID=$!

  # 서버 준비 대기
  MAX_WAIT=600
  WAITED=0
  until curl -s "http://localhost:$VLLM_PORT/health" > /dev/null 2>&1; do
    if [ "$WAITED" -ge "$MAX_WAIT" ]; then
      echo "[ERROR] judge 서버가 ${MAX_WAIT}초 내에 시작되지 않음."
      tail -20 "$VLLM_LOG"
      exit 1
    fi
    sleep 5; WAITED=$((WAITED + 5))
  done
  echo "[OK] 서버 준비 완료 (${WAITED}s)"

  BASE_URL="http://localhost:$VLLM_PORT/v1"
  API_KEY="EMPTY"

  # ── Step 1: Single-answer grading (한국어 프롬프트) ──────────────────────
  echo ""
  echo "[Step 1/$JUDGE_LABEL] Single-answer grading (--lang ko)..."
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

  # ── Step 2: Pairwise comparison (한국어 프롬프트) ────────────────────────
  echo ""
  echo "[Step 2/$JUDGE_LABEL] Pairwise comparison AB/BA (--lang ko)..."
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

  # ── Step 3: Reference-guided grading (한국어 프롬프트) ───────────────────
  echo ""
  echo "[Step 3/$JUDGE_LABEL] Reference-guided grading (--lang ko)..."
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

  # ── Step 4: 집계 ─────────────────────────────────────────────────────────
  echo ""
  echo "[Step 4/$JUDGE_LABEL] 집계..."
  python3 -m mtbench_repro.cli aggregate \
    --judgments-dir "$JUDGMENTS_DIR" \
    --questions-path "$QUESTIONS" \
    --output-csv "$OUTPUT_CSV" \
    --output-ref-csv "$OUTPUT_REF_CSV"
  echo "[OK] CSV: $OUTPUT_CSV"

  cleanup_server
  echo "[OK] $JUDGE_LABEL 서버 종료"

done

echo ""
echo "=============================="
echo " Gemma 2 한국어 Judge 전체 완료"
echo " 결과 파일:"
ls -lh "$KO_RESULTS_DIR"/results_ko_judge_gemma2_*.csv 2>/dev/null || \
ls -lh "$KO_RESULTS_DIR"/results_ko_*gemma2*.csv 2>/dev/null || echo "  (없음)"
echo ""
echo " 다음 단계: python3 scripts/translate/compare_en_ko.py"
echo " Date: $(date)"
echo "=============================="
