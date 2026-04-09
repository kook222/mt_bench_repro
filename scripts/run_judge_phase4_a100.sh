#!/bin/bash
# scripts/run_judge_phase4_a100.sh
#
# Phase 4: 교차 아키텍처 Judge 검증.
# Qwen 패밀리(Phase 3) 결과의 일반성을 InternLM2.5 패밀리로 교차 검증.
#
# 설계 원칙:
#   - Phase 3와 동일한 eval 모델 7개 사용 (비교 가능성 확보)
#   - InternLM2.5-7B-Chat / 20B-Chat 순차 실행
#   - 출력 경로: data/judgments_phase4/judge_internlm7b/ 등
#   - self-judge 없음 (InternLM2.5는 eval 모델 셋에 미포함)
#
# eval 모델 7개 (Phase 3와 동일):
#   Llama-3.1-8B-Instruct
#   SOLAR-10.7B-Instruct
#   gemma-2-9b-it
#   Yi-1.5-9B-Chat
#   Zephyr-7B-beta
#   Mistral-7B-Instruct-v0.3
#   Phi-3.5-mini-Instruct
#
# HuggingFace 모델 ID:
#   InternLM2.5-7B-Chat  : internlm/internlm2_5-7b-chat
#   InternLM2.5-20B-Chat : internlm/internlm2_5-20b-chat

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

MODEL_BASE_DIR="$HOME_DIR/models"
QUESTIONS="$PROJECT_DIR/data/mt_bench_questions.jsonl"
ANSWERS_DIR="$PROJECT_DIR/data/answers/"
PHASE4_DIR="$PROJECT_DIR/data/judgments_phase4"
VLLM_PORT=8000
VLLM_LOG="/tmp/vllm_judge_phase4.log"
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

# ── eval 모델 목록 (Phase 3와 동일) ──────────────────────────────────────────
EVAL_MODELS=(
  "Llama-3.1-8B-Instruct"
  "SOLAR-10.7B-Instruct"
  "gemma-2-9b-it"
  "Yi-1.5-9B-Chat"
  "Zephyr-7B-beta"
  "Mistral-7B-Instruct-v0.3"
  "Phi-3.5-mini-Instruct"
)

# ── judge 라인업 ────────────────────────────────────────────────────────────
# 형식: "judge_label:model_dir_name:gpu_util"
JUDGE_LIST=(
  "judge_internlm7b:internlm2_5-7b-chat:0.90"
  "judge_internlm20b:internlm2_5-20b-chat:0.92"
)

echo "=============================="
echo " Phase 4 Cross-Architecture Judge Validation"
echo " eval 모델: ${EVAL_MODELS[*]}"
echo " judge: ${JUDGE_LIST[*]}"
echo " Date: $(date)"
echo "=============================="

# ── 답변 파일 사전 확인 ─────────────────────────────────────────────────────
echo ""
echo "[Check] eval 모델 답변 파일 확인:"
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
  echo "[ERROR] ${MISSING}개 모델 답변 파일 없음."
  exit 1
fi

# ============================================================================
# judge 루프: 2종 순차 실행
# ============================================================================
for JUDGE_ENTRY in "${JUDGE_LIST[@]}"; do
  JUDGE_LABEL="${JUDGE_ENTRY%%:*}"
  REST="${JUDGE_ENTRY#*:}"
  JUDGE_MODEL_ID="${REST%%:*}"
  GPU_UTIL="${REST##*:}"

  JUDGE_MODEL_DIR="$MODEL_BASE_DIR/$JUDGE_MODEL_ID"
  JUDGMENTS_DIR="$PHASE4_DIR/$JUDGE_LABEL"
  OUTPUT_CSV="$PROJECT_DIR/data/results_phase4_${JUDGE_LABEL}.csv"

  echo ""
  echo "────────────────────────────────────────────"
  echo " Judge: $JUDGE_MODEL_ID ($JUDGE_LABEL)"
  echo " GPU util: $GPU_UTIL"
  echo " 출력: $JUDGMENTS_DIR"
  echo "────────────────────────────────────────────"

  # 모델 디렉토리 확인
  if [ ! -d "$JUDGE_MODEL_DIR" ]; then
    echo "[ERROR] judge 모델 없음: $JUDGE_MODEL_DIR"
    echo "        다운로드:"
    if [ "$JUDGE_LABEL" = "judge_internlm7b" ]; then
      echo "        hf download internlm/internlm2_5-7b-chat --local-dir $JUDGE_MODEL_DIR"
    else
      echo "        hf download internlm/internlm2_5-20b-chat --local-dir $JUDGE_MODEL_DIR"
    fi
    exit 1
  fi

  # vLLM 서버 시작 (20B는 fp8 양자화로 VRAM 절약)
  SERVE_ARGS=(
    "$JUDGE_MODEL_DIR"
    --served-model-name "$JUDGE_MODEL_ID"
    --api-key EMPTY
    --port "$VLLM_PORT"
    --max-model-len 8192
    --dtype auto
    --gpu-memory-utilization "$GPU_UTIL"
    --trust-remote-code
  )
  if [ "$JUDGE_LABEL" = "judge_internlm20b" ]; then
    SERVE_ARGS+=(--quantization fp8)
  fi
  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  vllm serve "${SERVE_ARGS[@]}" > "$VLLM_LOG" 2>&1 &
  VLLM_PID=$!

  # 서버 준비 대기
  MAX_WAIT=600
  WAITED=0
  until curl -s "http://localhost:$VLLM_PORT/health" > /dev/null 2>&1; do
    if [ "$WAITED" -ge "$MAX_WAIT" ]; then
      echo "[ERROR] judge 서버가 ${MAX_WAIT}초 내에 시작되지 않음."
      tail -20 "$VLLM_LOG"
      kill "$VLLM_PID" 2>/dev/null || true
      exit 1
    fi
    sleep 5; WAITED=$((WAITED + 5))
  done
  echo "[OK] 서버 준비 완료 (${WAITED}s)"

  BASE_URL="http://localhost:$VLLM_PORT/v1"
  API_KEY="EMPTY"

  # ── Step 1: Single-answer grading ────────────────────────────────────────
  echo ""
  echo "[Step 1/$JUDGE_LABEL] Single-answer grading..."
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
      --sleep 0.3
  done

  # ── Step 2: Pairwise comparison ──────────────────────────────────────────
  echo ""
  echo "[Step 2/$JUDGE_LABEL] Pairwise comparison (AB/BA swap)..."
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
        --sleep 0.5
    done
  done

  # ── Step 3: Reference-guided grading ─────────────────────────────────────
  echo ""
  echo "[Step 3/$JUDGE_LABEL] Reference-guided grading (math/reasoning/coding)..."
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
      --sleep 0.3
  done

  # ── Step 4: 집계 ─────────────────────────────────────────────────────────
  echo ""
  echo "[Step 4/$JUDGE_LABEL] 집계..."
  python3 -m mtbench_repro.cli aggregate \
    --judgments-dir "$JUDGMENTS_DIR" \
    --questions-path "$QUESTIONS" \
    --output-csv "$OUTPUT_CSV"
  echo "[OK] CSV: $OUTPUT_CSV"

  # judge 서버 종료
  cleanup_server
  echo "[OK] $JUDGE_LABEL 서버 종료"

done

echo ""
echo "=============================="
echo " Phase 4 Judge 전체 완료"
echo " 결과 파일:"
ls -lh "$PROJECT_DIR/data/results_phase4_"*.csv 2>/dev/null || echo "  (없음)"
echo ""
echo " 판정 디렉토리:"
ls -lhd "$PHASE4_DIR"/judge_* 2>/dev/null || echo "  (없음)"
echo ""
echo " 다음 단계: python3 scripts/analyze_phase4.py"
echo " Date: $(date)"
echo "=============================="
