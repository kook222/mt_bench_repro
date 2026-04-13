#!/bin/bash
# scripts/run/a100/run_generate_self_judge_a100.sh
#
# Self-Judge Bias 실험용 답변 생성.
#
# 목적:
#   Self-judge bias 증명을 위해 eval 모델에 LLaMA family + Qwen family를
#   둘 다 포함해야 한다. 이 스크립트는 기존 answers/에 없는 신규 모델들의
#   답변을 생성한다.
#
# Self-judge bias 증명 구조:
#   - LLaMA judge → LLaMA eval 모델 순위 상승 (vs GPT-mini 기준)
#   - Qwen  judge → Qwen  eval 모델 순위 상승 (vs GPT-mini 기준)
#   → 두 방향 모두 관찰되면 "self-judge bias는 구조적 문제"
#
# eval 모델 구성 (9개):
#   [LLaMA family]
#     Llama-2-7b-chat          ← 신규 생성
#     Llama-3.1-8B-Instruct    ← Phase 3에서 이미 생성됨
#   [Qwen family]
#     Qwen2.5-7B-Instruct      ← 신규 생성
#     Qwen2.5-14B-Instruct     ← 신규 생성
#   [중립 모델 — 기존 Phase 2/3 재사용]
#     Mistral-7B-Instruct-v0.3
#     gemma-2-9b-it
#     Phi-3.5-mini-Instruct
#     SOLAR-10.7B-Instruct
#     Zephyr-7B-beta
#
# 신규 생성이 필요한 모델: Llama-2-7b-chat, Qwen2.5-7B, Qwen2.5-14B

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
VLLM_PORT=8000
VLLM_LOG="/tmp/vllm_generate_self_judge.log"
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

# ── 기존 answers 확인 (재사용 가능 모델) ─────────────────────────────────────
echo ""
echo "[Check] 기존 답변 파일 (재사용):"
REUSE_MODELS=(
  "Llama-3.1-8B-Instruct"
  "Mistral-7B-Instruct-v0.3"
  "gemma-2-9b-it"
  "Phi-3.5-mini-Instruct"
  "SOLAR-10.7B-Instruct"
  "Zephyr-7B-beta"
)
for m in "${REUSE_MODELS[@]}"; do
  if [ -f "$ANSWERS_DIR/${m}.jsonl" ]; then
    n=$(wc -l < "$ANSWERS_DIR/${m}.jsonl" | tr -d ' ')
    echo "  [OK] $m ($n lines)"
  else
    echo "  [WARN] $m 파일 없음 — 이전 phase 먼저 실행 필요"
  fi
done

# ── 신규 생성 모델 목록 ─────────────────────────────────────────────────────
# 형식: "model_id:hf_model_id:max_model_len:gpu_util"
NEW_MODELS=(
  "Llama-2-7b-chat:meta-llama/Llama-2-7b-chat-hf:4096:0.88"
  "Qwen2.5-7B-Instruct:Qwen/Qwen2.5-7B-Instruct:8192:0.88"
  "Qwen2.5-14B-Instruct:Qwen/Qwen2.5-14B-Instruct:8192:0.90"
)

echo ""
echo "=============================="
echo " Self-Judge 실험 답변 생성"
echo " 신규 모델: Llama-2-7b-chat, Qwen2.5-7B, Qwen2.5-14B"
echo " Date: $(date)"
echo "=============================="

for ENTRY in "${NEW_MODELS[@]}"; do
  MODEL_ID="${ENTRY%%:*}"
  REST="${ENTRY#*:}"
  HF_ID="${REST%%:*}"
  REST="${REST#*:}"
  MAX_LEN="${REST%%:*}"
  GPU_UTIL="${REST##*:}"

  MODEL_DIR="$MODEL_BASE_DIR/$MODEL_ID"
  ANSWER_FILE="$ANSWERS_DIR/${MODEL_ID}.jsonl"

  echo ""
  echo "────────────────────────────────────────────"
  echo " 모델: $MODEL_ID"
  echo " HF: $HF_ID"
  echo "────────────────────────────────────────────"

  # 이미 생성된 경우 skip
  if [ -f "$ANSWER_FILE" ]; then
    n=$(wc -l < "$ANSWER_FILE" | tr -d ' ')
    if [ "$n" -ge 80 ]; then
      echo "[SKIP] 이미 완료: $ANSWER_FILE ($n lines)"
      continue
    fi
    echo "[RESUME] 부분 완료 ($n lines) → 이어서 생성"
  fi

  # 모델 디렉토리 확인
  if [ ! -d "$MODEL_DIR" ]; then
    echo "[ERROR] 모델 없음: $MODEL_DIR"
    echo "        다운로드: huggingface-cli download $HF_ID --local-dir $MODEL_DIR"
    exit 1
  fi

  # vLLM 서버 시작
  vllm serve "$MODEL_DIR" \
    --served-model-name "$MODEL_ID" \
    --api-key EMPTY \
    --port "$VLLM_PORT" \
    --max-model-len "$MAX_LEN" \
    --dtype auto \
    --gpu-memory-utilization "$GPU_UTIL" \
    > "$VLLM_LOG" 2>&1 &
  VLLM_PID=$!

  MAX_WAIT=300
  WAITED=0
  until curl -s "http://localhost:$VLLM_PORT/health" > /dev/null 2>&1; do
    if [ "$WAITED" -ge "$MAX_WAIT" ]; then
      echo "[ERROR] 서버 시작 실패"
      tail -20 "$VLLM_LOG"
      exit 1
    fi
    sleep 5; WAITED=$((WAITED + 5))
  done
  echo "[OK] 서버 준비 (${WAITED}s)"

  python3 -m mtbench_repro.cli generate \
    --questions "$QUESTIONS" \
    --answers-dir "$ANSWERS_DIR" \
    --model-id "$MODEL_ID" \
    --vllm-host localhost \
    --vllm-port "$VLLM_PORT" \
    --temperature 0.7 \
    --max-tokens 1024 \
    --sleep 0.3

  cleanup_server
  echo "[OK] $MODEL_ID 생성 완료"
done

echo ""
echo "=============================="
echo " 답변 생성 완료"
echo " 다음 단계:"
echo "   1. bash scripts/run/a100/run_judge_llama_a100.sh"
echo "   2. (Qwen judge는 Phase 3 기존 데이터 재사용)"
echo "   3. python3 scripts/analysis/analyze_self_judge_bias.py"
echo " Date: $(date)"
echo "=============================="
