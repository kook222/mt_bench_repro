#!/bin/bash
# scripts/run_judge_claude_api.sh
#
# Claude API judge 실행 스크립트.
# 주의:
#   - OpenAI API가 아니라 Anthropic Claude API를 사용한다.
#   - 내부적으로는 Anthropic native Python SDK(messages.create)를 사용한다.
#   - API key는 반드시 환경변수 ANTHROPIC_API_KEY로만 받는다.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "[ERROR] ANTHROPIC_API_KEY가 설정되어 있지 않습니다."
  echo "예: export ANTHROPIC_API_KEY='sk-ant-...'"
  exit 1
fi

export PYTHONPATH="$PROJECT_DIR/src:${PYTHONPATH:-}"

QUESTIONS="${QUESTIONS:-$PROJECT_DIR/data/mt_bench_questions.jsonl}"
ANSWERS_DIR="${ANSWERS_DIR:-$PROJECT_DIR/data/answers}"
OUTPUT_DIR="${OUTPUT_DIR:-$PROJECT_DIR/data/judgments_phase5/judge_claude_sonnet}"
OUTPUT_CSV="${OUTPUT_CSV:-$PROJECT_DIR/data/results_phase5_claude_sonnet.csv}"
OUTPUT_REF_CSV="${OUTPUT_REF_CSV:-$PROJECT_DIR/data/results_phase5_claude_sonnet_reference.csv}"
CLAUDE_MODEL="${CLAUDE_MODEL:-claude-sonnet-4-6}"
BASE_URL="${BASE_URL:-https://api.anthropic.com}"
SLEEP_SINGLE="${SLEEP_SINGLE:-0.8}"
SLEEP_PAIRWISE="${SLEEP_PAIRWISE:-1.2}"
SLEEP_REF="${SLEEP_REF:-0.8}"

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
echo " Claude Judge Run"
echo " Model: $CLAUDE_MODEL"
echo " Output dir: $OUTPUT_DIR"
echo " Models: ${MODELS[*]}"
echo "=============================="

echo ""
echo "[Step 1] Single-answer grading"
for MODEL_ID in "${MODELS[@]}"; do
  echo "  - $MODEL_ID"
  python3 -m mtbench_repro.cli judge-single \
    --provider anthropic \
    --questions "$QUESTIONS" \
    --answers-dir "$ANSWERS_DIR" \
    --output-dir "$OUTPUT_DIR" \
    --model-id "$MODEL_ID" \
    --judge-model "$CLAUDE_MODEL" \
    --api-key "$ANTHROPIC_API_KEY" \
    --base-url "$BASE_URL" \
    --sleep "$SLEEP_SINGLE"
done

echo ""
echo "[Step 2] Pairwise comparison"
for ((i=0; i<${#MODELS[@]}; i++)); do
  for ((j=i+1; j<${#MODELS[@]}; j++)); do
    MODEL_A="${MODELS[$i]}"
    MODEL_B="${MODELS[$j]}"
    echo "  - $MODEL_A vs $MODEL_B"
    python3 -m mtbench_repro.cli judge-pairwise \
      --provider anthropic \
      --questions "$QUESTIONS" \
      --answers-dir "$ANSWERS_DIR" \
      --output-dir "$OUTPUT_DIR" \
      --model-a "$MODEL_A" \
      --model-b "$MODEL_B" \
      --judge-model "$CLAUDE_MODEL" \
      --api-key "$ANTHROPIC_API_KEY" \
      --base-url "$BASE_URL" \
      --sleep "$SLEEP_PAIRWISE"
  done
done

echo ""
echo "[Step 3] Reference-guided grading"
for MODEL_ID in "${MODELS[@]}"; do
  echo "  - $MODEL_ID"
  python3 -m mtbench_repro.cli judge-reference \
    --provider anthropic \
    --questions "$QUESTIONS" \
    --answers-dir "$ANSWERS_DIR" \
    --output-dir "$OUTPUT_DIR" \
    --mode single \
    --model-id "$MODEL_ID" \
    --judge-model "$CLAUDE_MODEL" \
    --api-key "$ANTHROPIC_API_KEY" \
    --base-url "$BASE_URL" \
    --sleep "$SLEEP_REF"
done

echo ""
echo "[Step 4] Aggregate"
python3 -m mtbench_repro.cli aggregate \
  --judgments-dir "$OUTPUT_DIR" \
  --questions-path "$QUESTIONS" \
  --output-csv "$OUTPUT_CSV" \
  --output-ref-csv "$OUTPUT_REF_CSV"

echo ""
echo "=============================="
echo " Claude Judge Complete"
echo " Results:"
echo "   $OUTPUT_CSV"
echo "   $OUTPUT_REF_CSV"
echo "=============================="
