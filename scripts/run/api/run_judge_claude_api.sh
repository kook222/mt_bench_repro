#!/bin/bash
# scripts/run/api/run_judge_claude_api.sh
#
# GPT-4o-mini API judge 실행 스크립트.
# 주의:
#   - OpenAI API를 사용한다.
#   - API key는 반드시 환경변수 OPENAI_API_KEY로만 받는다.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_DIR"

if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "[ERROR] OPENAI_API_KEY가 설정되어 있지 않습니다."
  echo "예: export OPENAI_API_KEY='sk-...'"
  exit 1
fi

export PYTHONPATH="$PROJECT_DIR/src:${PYTHONPATH:-}"

QUESTIONS="${QUESTIONS:-$PROJECT_DIR/data/mt_bench_questions.jsonl}"
ANSWERS_DIR="${ANSWERS_DIR:-$PROJECT_DIR/data/answers}"
OUTPUT_DIR="${OUTPUT_DIR:-$PROJECT_DIR/data/judgments_phase5/judge_gpt4omini}"
OUTPUT_CSV="${OUTPUT_CSV:-$PROJECT_DIR/data/results_phase5_gpt4omini.csv}"
OUTPUT_REF_CSV="${OUTPUT_REF_CSV:-$PROJECT_DIR/data/results_phase5_gpt4omini_reference.csv}"
JUDGE_MODEL="${JUDGE_MODEL:-gpt-4o-mini}"
BASE_URL="${BASE_URL:-https://api.openai.com/v1}"
SLEEP_SINGLE="${SLEEP_SINGLE:-0.5}"
SLEEP_PAIRWISE="${SLEEP_PAIRWISE:-0.8}"
SLEEP_REF="${SLEEP_REF:-0.5}"
RUN_SINGLE="${RUN_SINGLE:-true}"
RUN_PAIRWISE="${RUN_PAIRWISE:-true}"
RUN_REFERENCE="${RUN_REFERENCE:-true}"
RUN_AGGREGATE="${RUN_AGGREGATE:-true}"

DEFAULT_MODELS=(
  "Llama-3.1-8B-Instruct"
  "SOLAR-10.7B-Instruct"
  "gemma-2-9b-it"
  "Yi-1.5-9B-Chat"
  "Zephyr-7B-beta"
  "Mistral-7B-Instruct-v0.3"
  "Phi-3.5-mini-Instruct"
)

if [ "$#" -gt 0 ]; then
  MODELS=("$@")
else
  MODELS=("${DEFAULT_MODELS[@]}")
fi

echo "=============================="
echo " GPT-4o-mini Judge Run"
echo " Model: $JUDGE_MODEL"
echo " Output dir: $OUTPUT_DIR"
echo " Models: ${MODELS[*]}"
echo "=============================="

if [ "$RUN_SINGLE" = "true" ]; then
  echo ""
  echo "[Step 1] Single-answer grading"
  for MODEL_ID in "${MODELS[@]}"; do
    echo "  - $MODEL_ID"
    python3 -m mtbench_repro.cli judge-single \
      --provider openai_compatible \
      --api-key "$OPENAI_API_KEY" \
      --base-url "$BASE_URL" \
      --questions "$QUESTIONS" \
      --answers-dir "$ANSWERS_DIR" \
      --output-dir "$OUTPUT_DIR" \
      --model-id "$MODEL_ID" \
      --judge-model "$JUDGE_MODEL" \
      --sleep "$SLEEP_SINGLE"
  done
fi

if [ "$RUN_PAIRWISE" = "true" ]; then
  echo ""
  echo "[Step 2] Pairwise comparison"
  for ((i=0; i<${#MODELS[@]}; i++)); do
    for ((j=i+1; j<${#MODELS[@]}; j++)); do
      MODEL_A="${MODELS[$i]}"
      MODEL_B="${MODELS[$j]}"
      echo "  - $MODEL_A vs $MODEL_B"
      python3 -m mtbench_repro.cli judge-pairwise \
        --provider openai_compatible \
        --api-key "$OPENAI_API_KEY" \
        --base-url "$BASE_URL" \
        --questions "$QUESTIONS" \
        --answers-dir "$ANSWERS_DIR" \
        --output-dir "$OUTPUT_DIR" \
        --model-a "$MODEL_A" \
        --model-b "$MODEL_B" \
        --judge-model "$JUDGE_MODEL" \
        --sleep "$SLEEP_PAIRWISE"
    done
  done
fi

if [ "$RUN_REFERENCE" = "true" ]; then
  echo ""
  echo "[Step 3] Reference-guided grading"
  for MODEL_ID in "${MODELS[@]}"; do
    echo "  - $MODEL_ID"
    python3 -m mtbench_repro.cli judge-reference \
      --provider openai_compatible \
      --api-key "$OPENAI_API_KEY" \
      --base-url "$BASE_URL" \
      --questions "$QUESTIONS" \
      --answers-dir "$ANSWERS_DIR" \
      --output-dir "$OUTPUT_DIR" \
      --mode single \
      --model-id "$MODEL_ID" \
      --judge-model "$JUDGE_MODEL" \
      --sleep "$SLEEP_REF"
  done
fi

if [ "$RUN_AGGREGATE" = "true" ]; then
  echo ""
  echo "[Step 4] Aggregate"
  python3 -m mtbench_repro.cli aggregate \
    --judgments-dir "$OUTPUT_DIR" \
    --questions-path "$QUESTIONS" \
    --output-csv "$OUTPUT_CSV" \
    --output-ref-csv "$OUTPUT_REF_CSV"
fi

echo ""
echo "=============================="
echo " GPT-4o-mini Judge Complete"
echo " Results:"
echo "   $OUTPUT_CSV"
echo "   $OUTPUT_REF_CSV"
echo "=============================="
