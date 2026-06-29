#!/bin/bash
# scripts/run/local/run_judge_gpt_local.sh
#
# GPT judge — EN + KO (로컬 실행)
# OpenAI API에 직접 연결 (vLLM 불필요)
#
# ============================================================
# ↓ 여기 두 줄만 수정
JUDGE_MODEL="gpt-4o-mini"   # "gpt-4o-mini" 또는 "gpt-4o"
JUDGE_LABEL="judge_gpt4omini"  # 결과 저장 디렉토리/파일명에 사용
# ↑ 나머지는 수정 불필요
# ============================================================
#
# 사용법:
#   export OPENAI_API_KEY="sk-..."
#   bash scripts/run/local/run_judge_gpt_local.sh
#
# 출력:
#   data/{en,ko}/judgments/gpt/$JUDGE_LABEL/
#   data/{en,ko}/results/results_{lang}_${JUDGE_LABEL}.csv

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_DIR"

export PYTHONPATH="$PROJECT_DIR/src"

OPENAI_BASE_URL="https://api.openai.com/v1"

EVAL_MODELS=(
  "EXAONE-3.5-7.8B-Instruct"
  "EEVE-Korean-Instruct-10.8B"
  "Llama-3.1-8B-Instruct"
  "gemma-2-9b-it"
  "Mistral-7B-Instruct-v0.3"
  "Phi-3.5-mini-Instruct"
)

echo "=============================="
echo " GPT Judge (로컬)"
echo " judge:  $JUDGE_MODEL"
echo " label:  $JUDGE_LABEL"
echo " models: ${#EVAL_MODELS[@]}개"
echo " date:   $(date)"
echo "=============================="

# API 키 확인
if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "[ERROR] OPENAI_API_KEY가 설정되지 않았습니다."
  echo "        export OPENAI_API_KEY=\"sk-...\""
  exit 1
fi
echo "[OK] OPENAI_API_KEY 확인됨"

# ============================================================================
# 언어별 judge 실행 함수
# ============================================================================
run_judge_for_lang() {
  local LANG="$1"
  local QUESTIONS="$2"
  local ANSWERS_DIR="$3"
  local JUDGE_DIR="$4"
  local RESULTS_DIR="$5"
  local OUTPUT_CSV="$6"
  local OUTPUT_REF_CSV="$7"

  mkdir -p "$JUDGE_DIR" "$RESULTS_DIR"

  echo ""
  echo "────────────────────────────────────────────"
  echo " [$(echo "$LANG" | tr '[:lower:]' '[:upper:]')] $JUDGE_MODEL Judge"
  echo " 질문:  $QUESTIONS"
  echo " 판정:  $JUDGE_DIR"
  echo "────────────────────────────────────────────"

  if [ ! -f "$QUESTIONS" ]; then
    echo "[ERROR] 질문 파일 없음: $QUESTIONS"; exit 1
  fi

  local MISSING=0
  for MODEL_ID in "${EVAL_MODELS[@]}"; do
    if [ ! -f "$ANSWERS_DIR/${MODEL_ID}.jsonl" ]; then
      echo "[ERROR] 답변 없음: $ANSWERS_DIR/${MODEL_ID}.jsonl"
      MISSING=$((MISSING + 1))
    fi
  done
  [ "$MISSING" -gt 0 ] && { echo "[ERROR] 답변 파일 ${MISSING}개 없음."; exit 1; }
  echo "[OK] 모든 답변 파일 확인됨"

  # ── Step 1: Single-answer grading ────────────────────────────────────────
  echo ""
  echo "[$(echo "$LANG" | tr '[:lower:]' '[:upper:]') 1/4] Single-answer grading..."
  for MODEL_ID in "${EVAL_MODELS[@]}"; do
    echo "  채점: $MODEL_ID"
    python3 -m mtbench_repro.cli judge-single \
      --questions      "$QUESTIONS" \
      --answers-dir    "$ANSWERS_DIR" \
      --output-dir     "$JUDGE_DIR" \
      --model-id       "$MODEL_ID" \
      --judge-model    "$JUDGE_MODEL" \
      --openai-base-url "$OPENAI_BASE_URL" \
      --openai-api-key  "$OPENAI_API_KEY" \
      --lang            "$LANG" \
      --sleep 0.3
  done
  echo "[OK] Single grading 완료"

  # ── Step 2: Pairwise comparison ───────────────────────────────────────────
  echo ""
  echo "[$(echo "$LANG" | tr '[:lower:]' '[:upper:]') 2/4] Pairwise comparison (AB + BA)..."
  for ((i=0; i<${#EVAL_MODELS[@]}; i++)); do
    for ((j=i+1; j<${#EVAL_MODELS[@]}; j++)); do
      MODEL_A="${EVAL_MODELS[$i]}"
      MODEL_B="${EVAL_MODELS[$j]}"
      echo "  비교: $MODEL_A vs $MODEL_B"
      python3 -m mtbench_repro.cli judge-pairwise \
        --questions      "$QUESTIONS" \
        --answers-dir    "$ANSWERS_DIR" \
        --output-dir     "$JUDGE_DIR" \
        --model-a        "$MODEL_A" \
        --model-b        "$MODEL_B" \
        --judge-model    "$JUDGE_MODEL" \
        --openai-base-url "$OPENAI_BASE_URL" \
        --openai-api-key  "$OPENAI_API_KEY" \
        --lang            "$LANG" \
        --sleep 0.5
    done
  done
  echo "[OK] Pairwise 완료"

  # ── Step 3: Reference-guided grading ─────────────────────────────────────
  echo ""
  echo "[$(echo "$LANG" | tr '[:lower:]' '[:upper:]') 3/4] Reference-guided grading..."
  for MODEL_ID in "${EVAL_MODELS[@]}"; do
    echo "  ref 채점: $MODEL_ID"
    python3 -m mtbench_repro.cli judge-reference \
      --questions      "$QUESTIONS" \
      --answers-dir    "$ANSWERS_DIR" \
      --output-dir     "$JUDGE_DIR" \
      --mode single \
      --model-id       "$MODEL_ID" \
      --judge-model    "$JUDGE_MODEL" \
      --openai-base-url "$OPENAI_BASE_URL" \
      --openai-api-key  "$OPENAI_API_KEY" \
      --lang            "$LANG" \
      --sleep 0.3
  done
  echo "[OK] Reference grading 완료"

  # ── Step 4: 집계 ─────────────────────────────────────────────────────────
  echo ""
  echo "[$(echo "$LANG" | tr '[:lower:]' '[:upper:]') 4/4] 집계..."
  python3 -m mtbench_repro.cli aggregate \
    --judgments-dir  "$JUDGE_DIR" \
    --questions-path "$QUESTIONS" \
    --output-csv     "$OUTPUT_CSV" \
    --output-ref-csv "$OUTPUT_REF_CSV"

  echo "[OK] $OUTPUT_CSV"
  echo "[OK] $OUTPUT_REF_CSV"
}

# ============================================================================
# EN
# ============================================================================
run_judge_for_lang \
  "en" \
  "$PROJECT_DIR/data/en/questions.jsonl" \
  "$PROJECT_DIR/data/en/answers" \
  "$PROJECT_DIR/data/en/judgments/gpt/$JUDGE_LABEL" \
  "$PROJECT_DIR/data/en/results" \
  "$PROJECT_DIR/data/en/results/results_en_${JUDGE_LABEL}.csv" \
  "$PROJECT_DIR/data/en/results/results_en_${JUDGE_LABEL}_ref.csv"

# ============================================================================
# KO
# ============================================================================
run_judge_for_lang \
  "ko" \
  "$PROJECT_DIR/data/ko/questions.jsonl" \
  "$PROJECT_DIR/data/ko/answers" \
  "$PROJECT_DIR/data/ko/judgments/gpt/$JUDGE_LABEL" \
  "$PROJECT_DIR/data/ko/results" \
  "$PROJECT_DIR/data/ko/results/results_ko_${JUDGE_LABEL}.csv" \
  "$PROJECT_DIR/data/ko/results/results_ko_${JUDGE_LABEL}_ref.csv"

# ============================================================================
# 완료
# ============================================================================
echo ""
echo "=============================="
echo " $JUDGE_MODEL Judge 완료"
echo ""
echo " EN 판정: data/en/judgments/gpt/$JUDGE_LABEL/"
echo " KO 판정: data/ko/judgments/gpt/$JUDGE_LABEL/"
echo " EN 결과: data/en/results/results_en_${JUDGE_LABEL}.csv"
echo " KO 결과: data/ko/results/results_ko_${JUDGE_LABEL}.csv"
echo ""
echo " 다음 단계: python3 scripts/translate/compare_en_ko.py"
echo " date: $(date)"
echo "=============================="
