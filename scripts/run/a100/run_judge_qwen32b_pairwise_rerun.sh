#!/bin/bash
# scripts/run/a100/run_judge_qwen32b_pairwise_rerun.sh
#
# Qwen2.5-32B pairwise 재실행 전용 스크립트.
#
# 기존 run에서 max_model_len=4096 → truncation 에러 다수 발생.
# 이 스크립트는 max_model_len=8192로 올려서 pairwise만 재실행.
#
# ⚠️  실행 전 반드시:
#     python3 scripts/tools/clean_truncation_errors.py
#     (truncation 에러 건 제거해야 resume이 올바르게 동작)
#
# 출력:
#   data/en/judgments/qwen/judge_32B/pairwise/  (영어)
#   data/ko/judgments/qwen/judge_32B/pairwise/  (한국어)

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
JUDGE_MODEL_ID="Qwen2.5-32B-Instruct"
JUDGE_MODEL_DIR="$MODEL_BASE_DIR/$JUDGE_MODEL_ID"
VLLM_PORT=8000
VLLM_LOG="/tmp/vllm_judge_qwen32b_rerun.log"
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
echo " Qwen2.5-32B Pairwise 재실행"
echo " max_model_len: 8192 (기존 4096 → 수정)"
echo " Date: $(date)"
echo "=============================="

# vLLM 서버 시작 (max_model_len 8192, AWQ, float16)
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

# ── 영어 pairwise ──────────────────────────────────────────────────────────────
EN_QUESTIONS="$PROJECT_DIR/data/en/questions.jsonl"
EN_ANSWERS_DIR="$PROJECT_DIR/data/en/answers/"
EN_JUDGMENTS_DIR="$PROJECT_DIR/data/en/judgments/qwen/judge_32B"
EN_RESULTS_DIR="$PROJECT_DIR/data/en/results"

echo ""
echo "[EN] Pairwise comparison AB/BA..."
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

echo "[OK] 영어 pairwise 완료"

# 영어 집계 (pairwise 포함 전체 재집계)
echo ""
echo "[EN] 집계..."
python3 -m mtbench_repro.cli aggregate \
  --judgments-dir "$EN_JUDGMENTS_DIR" \
  --questions-path "$EN_QUESTIONS" \
  --output-csv "$EN_RESULTS_DIR/results_phase3_judge_32B.csv" \
  --output-ref-csv "$EN_RESULTS_DIR/results_phase3_judge_32B_reference.csv"
echo "[OK] EN CSV 업데이트 완료"

# ── 한국어 pairwise ────────────────────────────────────────────────────────────
KO_QUESTIONS="$PROJECT_DIR/data/ko/questions.jsonl"
KO_ANSWERS_DIR="$PROJECT_DIR/data/ko/answers/"
KO_JUDGMENTS_DIR="$PROJECT_DIR/data/ko/judgments/qwen/judge_32B"
KO_RESULTS_DIR="$PROJECT_DIR/data/ko/results"

echo ""
echo "[KO] Pairwise comparison AB/BA (--lang ko)..."
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

echo "[OK] 한국어 pairwise 완료"

# 한국어 집계
echo ""
echo "[KO] 집계..."
python3 -m mtbench_repro.cli aggregate \
  --judgments-dir "$KO_JUDGMENTS_DIR" \
  --questions-path "$KO_QUESTIONS" \
  --output-csv "$KO_RESULTS_DIR/results_ko_judge_32B.csv" \
  --output-ref-csv "$KO_RESULTS_DIR/results_ko_judge_32B_reference.csv"
echo "[OK] KO CSV 업데이트 완료"

cleanup_server

echo ""
echo "=============================="
echo " Qwen2.5-32B Pairwise 재실행 완료"
echo " Date: $(date)"
echo "=============================="
