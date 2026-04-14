#!/bin/bash
# scripts/run/a100/run_judge_llama_a100.sh
#
# LLaMA family judge 실행 — 기존 Phase 3 eval 답변 재사용.
#
# 전체 분석 구조:
#   [그래프 1] Judge family 간 Kendall τ distance 히트맵
#     - Qwen 3개(7B/14B/32B) + LLaMA 2개(7B/13B) + GPT-mini 1개
#     - 같은 family judge끼리 τ distance가 낮으면 → family-level clustering
#
#   [그래프 2] Self-judge bias 분석
#     - 각 judge로 채점한 랭킹 vs GPT-mini(중립) 랭킹의 차이
#     - Llama-3.1-8B eval 모델이 LLaMA judge에서 몇 위 올라가는지 측정
#     - "self일 때 어떻게 달라지는가" → bias score per model
#
# eval 모델: Phase 3 기존 7개 답변 그대로 재사용 (새 생성 불필요)
#   Llama-3.1-8B-Instruct   ← LLaMA family eval (self-judge bias 핵심 대상)
#   SOLAR-10.7B-Instruct
#   gemma-2-9b-it
#   Yi-1.5-9B-Chat
#   Zephyr-7B-beta
#   Mistral-7B-Instruct-v0.3
#   Phi-3.5-mini-Instruct
#
# LLaMA judge 2종 (신규):
#   Llama-2-7b-chat  : meta-llama/Llama-2-7b-chat-hf
#   Llama-2-13b-chat : meta-llama/Llama-2-13b-chat-hf

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
QUESTIONS="$PROJECT_DIR/data/mt_bench_questions.jsonl"
ANSWERS_DIR="$PROJECT_DIR/data/answers/"
LLAMA_JUDGE_DIR="$PROJECT_DIR/data/judgments_llama_judge"
VLLM_PORT=8000
VLLM_LOG="/tmp/vllm_judge_llama.log"
VLLM_PID=""

cleanup_server() {
  if [ -n "${VLLM_PID:-}" ]; then
    kill "$VLLM_PID" 2>/dev/null || true
    wait "$VLLM_PID" 2>/dev/null || true
    VLLM_PID=""
  fi
}
trap cleanup_server EXIT INT TERM

# ── 경량 의존성 설치 ─────────────────────────────────────────────────────────
echo "[Init] 경량 의존성 설치..."
pip install openai tabulate tqdm --target /tmp/site-extra -q
export PYTHONPATH="/tmp/site-extra:$PROJECT_DIR/src"
echo "[Init] 완료."

# ── eval 모델 목록 (LLaMA + Qwen + 중립 모델 포함) ───────────────────────────
# Self-judge bias 증명을 위해 LLaMA family + Qwen family가 둘 다 필요:
#   - LLaMA judge가 LLaMA eval 모델을 유리하게 채점하는지
#   - Qwen  judge가 Qwen  eval 모델을 유리하게 채점하는지
#   두 방향 모두 확인해야 "구조적 편향" 주장 성립
# eval 모델 7개 확정 (self-judge bias 증명 구조):
#   LLaMA family 2개: Llama-2-7b-chat (judge와 동일 모델!), Llama-3.1-8B
#   Qwen  family 1개: Qwen2.5-7B (Qwen judge의 same-family)
#   neutral      4개: gemma, Mistral, Phi, Zephyr
# Phase 3 기존 7개 답변 그대로 재사용 — 새 생성 불필요
EVAL_MODELS=(
  "Llama-3.1-8B-Instruct"     # LLaMA family (self-judge bias 측정 대상)
  "SOLAR-10.7B-Instruct"
  "gemma-2-9b-it"
  "Yi-1.5-9B-Chat"
  "Zephyr-7B-beta"
  "Mistral-7B-Instruct-v0.3"
  "Phi-3.5-mini-Instruct"
)

# ── judge 라인업: LLaMA 2 family (7B → 13B) ──────────────────────────────────
# Qwen처럼 동일 세대 내 크기별 비교 (7B / 13B)
# 70B는 A100 40GB에서 AWQ도 OOM → 제외
JUDGE_LIST=(
  "judge_7B:Llama-2-7b-chat:none:0.88"
  "judge_13B:Llama-2-13b-chat:none:0.92"
)

echo "=============================="
echo " LLaMA Judge — Self-Judge Bias 실험"
echo " eval 모델: ${EVAL_MODELS[*]}"
echo " judge 2종: judge_8B, judge_70B"
echo " Date: $(date)"
echo "=============================="

# ── 답변 파일 사전 확인 ──────────────────────────────────────────────────────
echo ""
echo "[Check] eval 모델 답변 파일 확인:"
MISSING=0
for MODEL_ID in "${EVAL_MODELS[@]}"; do
  if [ -f "$ANSWERS_DIR/${MODEL_ID}.jsonl" ]; then
    n=$(wc -l < "$ANSWERS_DIR/${MODEL_ID}.jsonl" | tr -d ' ')
    echo "  [OK] $MODEL_ID ($n lines)"
  else
    echo "  [ERROR] $MODEL_ID 답변 없음 — run_generate_phase3_a100.sh 먼저 실행"
    MISSING=$((MISSING + 1))
  fi
done
if [ "$MISSING" -gt 0 ]; then
  echo "[ERROR] $MISSING개 모델 답변 없음. 종료."
  exit 1
fi

# ============================================================================
# judge 루프: 8B → 70B 순차 실행
# ============================================================================
for JUDGE_ENTRY in "${JUDGE_LIST[@]}"; do
  JUDGE_LABEL="${JUDGE_ENTRY%%:*}"
  REST="${JUDGE_ENTRY#*:}"
  JUDGE_MODEL_ID="${REST%%:*}"
  REST="${REST#*:}"
  QUANT="${REST%%:*}"
  GPU_UTIL="${REST##*:}"

  JUDGE_MODEL_DIR="$MODEL_BASE_DIR/$JUDGE_MODEL_ID"
  JUDGMENTS_DIR="$LLAMA_JUDGE_DIR/$JUDGE_LABEL"
  OUTPUT_CSV="$PROJECT_DIR/data/results_llama_judge_${JUDGE_LABEL}.csv"

  echo ""
  echo "────────────────────────────────────────────"
  echo " Judge: $JUDGE_MODEL_ID ($JUDGE_LABEL)"
  echo " 양자화: $QUANT | GPU util: $GPU_UTIL"
  echo " 출력: $JUDGMENTS_DIR"
  echo "────────────────────────────────────────────"

  # 모델 디렉토리 확인
  if [ ! -d "$JUDGE_MODEL_DIR" ]; then
    echo "[ERROR] judge 모델 없음: $JUDGE_MODEL_DIR"
    if [ "$QUANT" = "awq" ]; then
      echo "        다운로드: huggingface-cli download meta-llama/Llama-3.3-70B-Instruct-AWQ --local-dir $JUDGE_MODEL_DIR"
    else
      echo "        다운로드: huggingface-cli download meta-llama/Llama-3.1-8B-Instruct --local-dir $JUDGE_MODEL_DIR"
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
      --dtype auto \
      --gpu-memory-utilization "$GPU_UTIL" \
      > "$VLLM_LOG" 2>&1 &
  fi
  VLLM_PID=$!

  # 서버 준비 대기 (최대 600초)
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

  # ── Step 1: Single-answer grading ────────────────────────────────────────
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
  echo "[Step 4/$JUDGE_LABEL] 집계..."
  python3 -m mtbench_repro.cli aggregate \
    --judgments-dir "$JUDGMENTS_DIR" \
    --questions-path "$QUESTIONS" \
    --output-csv "$OUTPUT_CSV"
  echo "[OK] CSV: $OUTPUT_CSV"

  cleanup_server
  echo "[OK] $JUDGE_LABEL 서버 종료"
done

echo ""
echo "=============================="
echo " LLaMA Judge 전체 완료"
echo " 결과 파일:"
ls -lh "$PROJECT_DIR/data/results_llama_judge_"*.csv 2>/dev/null || echo "  (없음)"
echo ""
echo " 다음 단계: python3 scripts/analysis/analyze_self_judge_bias.py"
echo " Date: $(date)"
echo "=============================="
