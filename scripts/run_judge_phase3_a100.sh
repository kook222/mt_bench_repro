#!/bin/bash
# scripts/run_judge_phase3_a100.sh
#
# Phase 3: Judge 크기 스케일링 실험.
# Qwen2.5 단일 패밀리(7B / 14B / 32B / 72B)로 순차 judge 실행.
#
# 설계 원칙:
#   - judge 1개씩 vLLM 올리고 → 전 모델 judge → 서버 내리고 → 다음 judge
#   - 출력 경로를 judge 크기별로 분리: data/judgments_phase3/judge_7B/ 등
#   - 32B / 72B는 AWQ 4-bit 양자화 사용 (A100 40GB VRAM 제약)
#   - 14B는 Phase 2와 eval 모델 셋이 다르므로(Llama 추가, Qwen 제거) 재실행
#
# eval 모델 7개 (Phase 2에서 변경):
#   Llama-3.1-8B-Instruct  (신규 — Qwen2.5-7B 대체)
#   SOLAR-10.7B-Instruct   (Phase 2 재사용)
#   gemma-2-9b-it          (Phase 2 재사용)
#   Yi-1.5-9B-Chat         (Phase 2 재사용)
#   Zephyr-7B-beta         (Phase 2 재사용)
#   Mistral-7B-Instruct-v0.3 (Phase 2 재사용)
#   Phi-3.5-mini-Instruct  (Phase 2 재사용)
#
# HuggingFace 모델 ID:
#   Qwen2.5-7B-Instruct  : Qwen/Qwen2.5-7B-Instruct
#   Qwen2.5-14B-Instruct : Qwen/Qwen2.5-14B-Instruct
#   Qwen2.5-32B-Instruct : Qwen/Qwen2.5-32B-Instruct-AWQ  (AWQ 4-bit)
#   Qwen2.5-72B-Instruct : Qwen/Qwen2.5-72B-Instruct-AWQ  (AWQ 4-bit)

set -e

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
PHASE3_DIR="$PROJECT_DIR/data/judgments_phase3"
VLLM_PORT=8000
VLLM_LOG="$HOME_DIR/vllm_judge_phase3.log"

# ── 경량 의존성 설치 (vllm/vllm-openai 이미지 전용) ──────────────────────
echo "[Init] 경량 의존성 설치..."
pip install openai tabulate tqdm --target /tmp/site-extra -q
export PYTHONPATH="/tmp/site-extra:$PROJECT_DIR/src"
echo "[Init] 완료."

# ── eval 모델 목록 ──────────────────────────────────────────────────────────
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
# 형식: "judge_label:model_dir_name:quantization_flag:gpu_util"
#   quantization_flag: "none" 또는 "awq"
#   gpu_util: 72B AWQ는 0.85로 낮춤 (40GB 한계 근접)
JUDGE_LIST=(
  "judge_7B:Qwen2.5-7B-Instruct:none:0.90"
  "judge_14B:Qwen2.5-14B-Instruct:none:0.90"
  "judge_32B:Qwen2.5-32B-Instruct:awq:0.90"
  "judge_72B:Qwen2.5-72B-Instruct:awq:0.85"
)

echo "=============================="
echo " Phase 3 Judge Scaling Experiment"
echo " eval 모델: ${EVAL_MODELS[*]}"
echo " judge 4종: ${JUDGE_LIST[*]}"
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
  echo "[ERROR] $MISSING개 모델 답변 파일 없음. 먼저 run_generate_phase3_a100.sh 실행."
  exit 1
fi

# ============================================================================
# judge 루프: 4종 순차 실행
# ============================================================================
for JUDGE_ENTRY in "${JUDGE_LIST[@]}"; do
  JUDGE_LABEL="${JUDGE_ENTRY%%:*}"
  REST="${JUDGE_ENTRY#*:}"
  JUDGE_MODEL_ID="${REST%%:*}"
  REST="${REST#*:}"
  QUANT="${REST%%:*}"
  GPU_UTIL="${REST##*:}"

  JUDGE_MODEL_DIR="$MODEL_BASE_DIR/$JUDGE_MODEL_ID"
  JUDGMENTS_DIR="$PHASE3_DIR/$JUDGE_LABEL"
  OUTPUT_CSV="$PROJECT_DIR/data/results_phase3_${JUDGE_LABEL}.csv"

  echo ""
  echo "────────────────────────────────────────────"
  echo " Judge: $JUDGE_MODEL_ID ($JUDGE_LABEL)"
  echo " 양자화: $QUANT | GPU util: $GPU_UTIL"
  echo " 출력: $JUDGMENTS_DIR"
  echo "────────────────────────────────────────────"

  # 모델 디렉토리 확인
  if [ ! -d "$JUDGE_MODEL_DIR" ]; then
    echo "[ERROR] judge 모델 없음: $JUDGE_MODEL_DIR"
    echo "        다운로드:"
    if [ "$QUANT" = "awq" ]; then
      echo "        hf download Qwen/${JUDGE_MODEL_ID}-AWQ --local-dir $JUDGE_MODEL_DIR"
    else
      echo "        hf download Qwen/${JUDGE_MODEL_ID} --local-dir $JUDGE_MODEL_DIR"
    fi
    exit 1
  fi

  # vLLM 서버 시작 (양자화 여부에 따라 분기)
  if [ "$QUANT" = "awq" ]; then
    vllm serve "$JUDGE_MODEL_DIR" \
      --served-model-name "$JUDGE_MODEL_ID" \
      --api-key EMPTY \
      --port "$VLLM_PORT" \
      --max-model-len 8192 \
      --dtype auto \
      --quantization awq \
      --gpu-memory-utilization "$GPU_UTIL" \
      > "$VLLM_LOG" 2>&1 &
  else
    vllm serve "$JUDGE_MODEL_DIR" \
      --served-model-name "$JUDGE_MODEL_ID" \
      --api-key EMPTY \
      --port "$VLLM_PORT" \
      --max-model-len 8192 \
      --dtype auto \
      --gpu-memory-utilization "$GPU_UTIL" \
      > "$VLLM_LOG" 2>&1 &
  fi
  VLLM_PID=$!

  # 서버 준비 대기 (72B AWQ는 로드 시간이 길어 최대 600초)
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
    --output-csv "$OUTPUT_CSV"
  echo "[OK] CSV: $OUTPUT_CSV"

  # judge 서버 종료
  kill "$VLLM_PID" 2>/dev/null || true
  wait "$VLLM_PID" 2>/dev/null || true
  echo "[OK] $JUDGE_LABEL 서버 종료"

done

echo ""
echo "=============================="
echo " Phase 3 Judge 전체 완료"
echo " 결과 파일:"
ls -lh "$PROJECT_DIR/data/results_phase3_"*.csv 2>/dev/null || echo "  (없음)"
echo ""
echo " 판정 디렉토리:"
ls -lhd "$PHASE3_DIR"/judge_* 2>/dev/null || echo "  (없음)"
echo ""
echo " 다음 단계: python3 scripts/analyze_phase3.py"
echo " Date: $(date)"
echo "=============================="
