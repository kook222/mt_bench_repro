#!/bin/bash
# scripts/run/a100/run_judge_exaone32b_a100.sh
#
# EXAONE-3.5-32B-Instruct-AWQ judge 실험 — 영어 + 한국어.
#
# 목적:
#   - Qwen 계열 외 다른 judge family 신뢰도 비교
#   - 한국어 특화 32B 모델(EXAONE)이 judge로서 Qwen 32B와 어떻게 다른지 측정
#   - EXAONE eval 모델(7.8B)과의 self-judge bias 분석
#
# 모델: LGAI-EXAONE/EXAONE-3.5-32B-Instruct-AWQ
#   - AWQ 양자화 → --dtype float16 필수
#   - custom_code 사용 → --trust-remote-code 필수
#
# 출력:
#   data/en/judgments/exaone/judge_32B/   (영어)
#   data/ko/judgments/exaone/judge_32B/   (한국어)

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
JUDGE_MODEL_ID="EXAONE-3.5-32B-Instruct-AWQ"
JUDGE_MODEL_DIR="$MODEL_BASE_DIR/$JUDGE_MODEL_ID"
VLLM_PORT=8000
VLLM_LOG="/tmp/vllm_judge_exaone32b.log"
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

# 모델 확인
if [ ! -d "$JUDGE_MODEL_DIR" ]; then
  echo "[ERROR] judge 모델 없음: $JUDGE_MODEL_DIR"
  echo "        huggingface-cli download LGAI-EXAONE/EXAONE-3.5-32B-Instruct-AWQ --local-dir $JUDGE_MODEL_DIR"
  exit 1
fi

EVAL_MODELS=(
  "Llama-3.1-8B-Instruct"
  "EEVE-Korean-Instruct-10.8B"
  "EXAONE-3.5-7.8B-Instruct"
  "gemma-2-9b-it"
  "Mistral-7B-Instruct-v0.3"
  "Phi-3.5-mini-Instruct"
)

echo "=============================="
echo " EXAONE-3.5-32B-Instruct-AWQ Judge 실험"
echo " 영어 + 한국어 순차 실행"
echo " Date: $(date)"
echo "=============================="

# vLLM 서버 시작
# - AWQ: --dtype float16 필수 (auto/bfloat16 사용 금지)
# - --trust-remote-code: EXAONE custom_code 필수
# - max-model-len 8192: judge 프롬프트 길이 여유분 확보
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
vllm serve "$JUDGE_MODEL_DIR" \
  --served-model-name "$JUDGE_MODEL_ID" \
  --api-key EMPTY \
  --port "$VLLM_PORT" \
  --max-model-len 8192 \
  --dtype float16 \
  --quantization awq \
  --trust-remote-code \
  --gpu-memory-utilization 0.95 \
  --enforce-eager \
  --max-num-seqs 1 \
  > "$VLLM_LOG" 2>&1 &
VLLM_PID=$!

# 서버 대기
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

# ── 영어 judge ──────────────────────────────────────────────────────────────
EN_QUESTIONS="$PROJECT_DIR/data/en/questions.jsonl"
EN_ANSWERS_DIR="$PROJECT_DIR/data/en/answers/"
EN_JUDGMENTS_DIR="$PROJECT_DIR/data/en/judgments/exaone/judge_32B"
EN_RESULTS_DIR="$PROJECT_DIR/data/en/results"

mkdir -p "$EN_JUDGMENTS_DIR"

# 영어 답변 파일 확인
echo ""
echo "[EN] eval 모델 답변 파일 확인:"
MISSING=0
for MODEL_ID in "${EVAL_MODELS[@]}"; do
  if [ -f "$EN_ANSWERS_DIR/${MODEL_ID}.jsonl" ]; then
    n=$(wc -l < "$EN_ANSWERS_DIR/${MODEL_ID}.jsonl" | tr -d ' ')
    echo "  [OK] $MODEL_ID ($n lines)"
  else
    echo "  [ERROR] $MODEL_ID 답변 없음"
    MISSING=$((MISSING + 1))
  fi
done
if [ "$MISSING" -gt 0 ]; then
  echo "[ERROR] $MISSING개 모델 답변 없음. 종료."
  exit 1
fi

# Step 1: EN Single-answer grading
echo ""
echo "[EN Step 1] Single-answer grading..."
for MODEL_ID in "${EVAL_MODELS[@]}"; do
  echo "  채점: $MODEL_ID"
  python3 -m mtbench_repro.cli judge-single \
    --questions "$EN_QUESTIONS" \
    --answers-dir "$EN_ANSWERS_DIR" \
    --output-dir "$EN_JUDGMENTS_DIR" \
    --model-id "$MODEL_ID" \
    --judge-model "$JUDGE_MODEL_ID" \
    --openai-base-url "$BASE_URL" \
    --openai-api-key "$API_KEY" \
    --sleep 0.3
done
echo "[OK] EN single-answer grading 완료"

# Step 2: EN Pairwise comparison
echo ""
echo "[EN Step 2] Pairwise comparison AB/BA..."
for ((i=0; i<${#EVAL_MODELS[@]}; i++)); do
  for ((j=i+1; j<${#EVAL_MODELS[@]}; j++)); do
    MODEL_A="${EVAL_MODELS[$i]}"
    MODEL_B="${EVAL_MODELS[$j]}"
    echo "  비교: $MODEL_A vs $MODEL_B"
    python3 -m mtbench_repro.cli judge-pairwise \
      --questions "$EN_QUESTIONS" \
      --answers-dir "$EN_ANSWERS_DIR" \
      --output-dir "$EN_JUDGMENTS_DIR" \
      --model-a "$MODEL_A" \
      --model-b "$MODEL_B" \
      --judge-model "$JUDGE_MODEL_ID" \
      --openai-base-url "$BASE_URL" \
      --openai-api-key "$API_KEY" \
      --sleep 0.5
  done
done
echo "[OK] EN pairwise 완료"

# Step 3: EN Reference-guided grading
echo ""
echo "[EN Step 3] Reference-guided grading..."
for MODEL_ID in "${EVAL_MODELS[@]}"; do
  echo "  reference 채점: $MODEL_ID"
  python3 -m mtbench_repro.cli judge-reference \
    --questions "$EN_QUESTIONS" \
    --answers-dir "$EN_ANSWERS_DIR" \
    --output-dir "$EN_JUDGMENTS_DIR" \
    --mode single \
    --model-id "$MODEL_ID" \
    --judge-model "$JUDGE_MODEL_ID" \
    --openai-base-url "$BASE_URL" \
    --openai-api-key "$API_KEY" \
    --sleep 0.3
done
echo "[OK] EN reference grading 완료"

# Step 4: EN 집계
echo ""
echo "[EN Step 4] 집계..."
python3 -m mtbench_repro.cli aggregate \
  --judgments-dir "$EN_JUDGMENTS_DIR" \
  --questions-path "$EN_QUESTIONS" \
  --output-csv "$EN_RESULTS_DIR/results_phase3_judge_exaone32B.csv" \
  --output-ref-csv "$EN_RESULTS_DIR/results_phase3_judge_exaone32B_reference.csv"
echo "[OK] EN CSV 완료"

# ── 한국어 judge ──────────────────────────────────────────────────────────────
KO_QUESTIONS="$PROJECT_DIR/data/ko/questions.jsonl"
KO_ANSWERS_DIR="$PROJECT_DIR/data/ko/answers/"
KO_JUDGMENTS_DIR="$PROJECT_DIR/data/ko/judgments/exaone/judge_32B"
KO_RESULTS_DIR="$PROJECT_DIR/data/ko/results"

mkdir -p "$KO_JUDGMENTS_DIR"

# 한국어 답변 파일 확인
echo ""
echo "[KO] eval 모델 한국어 답변 파일 확인:"
MISSING=0
for MODEL_ID in "${EVAL_MODELS[@]}"; do
  if [ -f "$KO_ANSWERS_DIR/${MODEL_ID}.jsonl" ]; then
    n=$(wc -l < "$KO_ANSWERS_DIR/${MODEL_ID}.jsonl" | tr -d ' ')
    echo "  [OK] $MODEL_ID ($n lines)"
  else
    echo "  [ERROR] $MODEL_ID 한국어 답변 없음"
    MISSING=$((MISSING + 1))
  fi
done
if [ "$MISSING" -gt 0 ]; then
  echo "[ERROR] $MISSING개 모델 한국어 답변 없음. 종료."
  exit 1
fi

# Step 1: KO Single-answer grading
echo ""
echo "[KO Step 1] Single-answer grading (--lang ko)..."
for MODEL_ID in "${EVAL_MODELS[@]}"; do
  echo "  채점: $MODEL_ID"
  python3 -m mtbench_repro.cli judge-single \
    --questions "$KO_QUESTIONS" \
    --answers-dir "$KO_ANSWERS_DIR" \
    --output-dir "$KO_JUDGMENTS_DIR" \
    --model-id "$MODEL_ID" \
    --judge-model "$JUDGE_MODEL_ID" \
    --openai-base-url "$BASE_URL" \
    --openai-api-key "$API_KEY" \
    --lang ko \
    --sleep 0.3
done
echo "[OK] KO single-answer grading 완료"

# Step 2: KO Pairwise comparison
echo ""
echo "[KO Step 2] Pairwise comparison AB/BA (--lang ko)..."
for ((i=0; i<${#EVAL_MODELS[@]}; i++)); do
  for ((j=i+1; j<${#EVAL_MODELS[@]}; j++)); do
    MODEL_A="${EVAL_MODELS[$i]}"
    MODEL_B="${EVAL_MODELS[$j]}"
    echo "  비교: $MODEL_A vs $MODEL_B"
    python3 -m mtbench_repro.cli judge-pairwise \
      --questions "$KO_QUESTIONS" \
      --answers-dir "$KO_ANSWERS_DIR" \
      --output-dir "$KO_JUDGMENTS_DIR" \
      --model-a "$MODEL_A" \
      --model-b "$MODEL_B" \
      --judge-model "$JUDGE_MODEL_ID" \
      --openai-base-url "$BASE_URL" \
      --openai-api-key "$API_KEY" \
      --lang ko \
      --sleep 0.5
  done
done
echo "[OK] KO pairwise 완료"

# Step 3: KO Reference-guided grading
echo ""
echo "[KO Step 3] Reference-guided grading (--lang ko)..."
for MODEL_ID in "${EVAL_MODELS[@]}"; do
  echo "  reference 채점: $MODEL_ID"
  python3 -m mtbench_repro.cli judge-reference \
    --questions "$KO_QUESTIONS" \
    --answers-dir "$KO_ANSWERS_DIR" \
    --output-dir "$KO_JUDGMENTS_DIR" \
    --mode single \
    --model-id "$MODEL_ID" \
    --judge-model "$JUDGE_MODEL_ID" \
    --openai-base-url "$BASE_URL" \
    --openai-api-key "$API_KEY" \
    --lang ko \
    --sleep 0.3
done
echo "[OK] KO reference grading 완료"

# Step 4: KO 집계
echo ""
echo "[KO Step 4] 집계..."
python3 -m mtbench_repro.cli aggregate \
  --judgments-dir "$KO_JUDGMENTS_DIR" \
  --questions-path "$KO_QUESTIONS" \
  --output-csv "$KO_RESULTS_DIR/results_ko_judge_exaone32B.csv" \
  --output-ref-csv "$KO_RESULTS_DIR/results_ko_judge_exaone32B_reference.csv"
echo "[OK] KO CSV 완료"

cleanup_server

echo ""
echo "=============================="
echo " EXAONE-3.5-32B Judge 전체 완료"
echo " EN: $EN_RESULTS_DIR/results_phase3_judge_exaone32B*.csv"
echo " KO: $KO_RESULTS_DIR/results_ko_judge_exaone32B*.csv"
echo " Date: $(date)"
echo "=============================="
