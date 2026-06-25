#!/bin/bash
# scripts/run/a100/run_generate_phase3_a100.sh
#
# 영어 MT-Bench 신규 모델 2개 답변 생성.
#
# eval 모델 6개 구성:
#   기존 4개 (answers 재사용): Llama-3.1-8B, gemma-2-9b, Mistral-7B, Phi-3.5-mini
#   신규 2개 (생성 필요):
#     EEVE-Korean-Instruct-10.8B  ← 한국어 특화 (SOLAR 기반 fine-tune)
#     EXAONE-3.5-7.8B-Instruct    ← 한국어 특화 (LG AI Research)
#
# EEVE-Korean: SOLAR와 동일한 ### User/Assistant 템플릿 사용
#              → solar_chat_template.jinja 재사용
#
# 전제:
#   - 두 모델이 MODEL_BASE_DIR에 다운로드되어 있어야 함.
#   - 기존 4개 모델 answers가 data/en/answers/ 에 있어야 함.

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
QUESTIONS="$PROJECT_DIR/data/en/questions.jsonl"
ANSWERS_DIR="$PROJECT_DIR/data/en/answers/"
VLLM_PORT=8000
VLLM_LOG="/tmp/vllm_generate_phase3.log"
VLLM_PID=""

cleanup_server() {
  if [ -n "${VLLM_PID:-}" ]; then
    kill "$VLLM_PID" 2>/dev/null || true
    wait "$VLLM_PID" 2>/dev/null || true
    VLLM_PID=""
  fi
}
trap cleanup_server EXIT INT TERM

# ── 경량 의존성 설치 (vllm/vllm-openai 이미지 전용) ──────────────────────
echo "[Init] 경량 의존성 설치..."
pip install openai tabulate tqdm --target /tmp/site-extra -q
export PYTHONPATH="/tmp/site-extra:$PROJECT_DIR/src"
echo "[Init] 완료."

# ── 신규 모델 목록 (기존 4개는 answers 재사용) ───────────────────────────────
# 형식: "모델_ID:HF_ID:max-model-len:gpu-util:chat_template"
# chat_template: "solar" = solar_chat_template.jinja 사용, "default" = vLLM 자동
SOLAR_TEMPLATE="$SCRIPT_DIR/solar_chat_template.jinja"

declare -a MODEL_LIST=(
  "EEVE-Korean-Instruct-10.8B:yanolja/EEVE-Korean-Instruct-10.8B-v1.0:4096:0.90:solar"
  "EXAONE-3.5-7.8B-Instruct:LGAI-MEDIUS/EXAONE-3.5-7.8B-Instruct:4096:0.90:default"
)

echo "=============================="
echo " 영어 MT-Bench 신규 답변 생성"
echo " 신규 모델: ${#MODEL_LIST[@]}개 (EEVE-Korean, EXAONE-3.5)"
echo " 기존 4개 모델 answers 재사용"
echo " Date: $(date)"
echo "=============================="

# 기존 answers 확인
echo ""
echo "[Info] 기존 답변 파일 확인:"
for m in Llama-3.1-8B-Instruct gemma-2-9b-it Mistral-7B-Instruct-v0.3 Phi-3.5-mini-Instruct; do
  if [ -f "$ANSWERS_DIR/${m}.jsonl" ]; then
    n=$(wc -l < "$ANSWERS_DIR/${m}.jsonl" | tr -d ' ')
    echo "  [OK] $m ($n lines)"
  else
    echo "  [WARN] $m 파일 없음"
  fi
done
echo ""

mkdir -p "$ANSWERS_DIR"

# ── 모델별 순차 실행 ──────────────────────────────────────────────────────────
for ENTRY in "${MODEL_LIST[@]}"; do
  MODEL_ID="${ENTRY%%:*}"
  REST="${ENTRY#*:}"
  HF_ID="${REST%%:*}"
  REST="${REST#*:}"
  MAX_LEN="${REST%%:*}"
  REST="${REST#*:}"
  GPU_UTIL="${REST%%:*}"
  TMPL="${REST##*:}"

  MODEL_DIR="$MODEL_BASE_DIR/$MODEL_ID"
  ANSWER_FILE="$ANSWERS_DIR/${MODEL_ID}.jsonl"

  echo ""
  echo "────────────────────────────────────────────"
  echo " 모델: $MODEL_ID"
  echo " HF: $HF_ID"
  echo "────────────────────────────────────────────"

  if [ ! -d "$MODEL_DIR" ]; then
    echo "[ERROR] 모델 디렉토리 없음: $MODEL_DIR"
    echo "        huggingface-cli download $HF_ID --local-dir $MODEL_DIR"
    exit 1
  fi

  if [ -f "$ANSWER_FILE" ]; then
    EXISTING=$(wc -l < "$ANSWER_FILE" | tr -d ' ')
    echo "[INFO] 기존 답변 ${EXISTING}줄 — resume 모드."
  fi

  # vLLM 서버 시작
  CHAT_TEMPLATE_ARG=""
  if [ "$TMPL" = "solar" ]; then
    CHAT_TEMPLATE_ARG="--chat-template $SOLAR_TEMPLATE"
    echo "[INFO] solar chat template 적용"
  fi

  vllm serve "$MODEL_DIR" \
    --served-model-name "$MODEL_ID" \
    --api-key EMPTY \
    --port "$VLLM_PORT" \
    --max-model-len "$MAX_LEN" \
    --dtype auto \
    --gpu-memory-utilization "$GPU_UTIL" \
    $CHAT_TEMPLATE_ARG \
    > "$VLLM_LOG" 2>&1 &
  VLLM_PID=$!

  MAX_WAIT=300
  WAITED=0
  until curl -s "http://localhost:$VLLM_PORT/health" > /dev/null 2>&1; do
    if [ "$WAITED" -ge "$MAX_WAIT" ]; then
      echo "[ERROR] vLLM 서버가 ${MAX_WAIT}초 내에 시작되지 않음."
      tail -20 "$VLLM_LOG"
      exit 1
    fi
    sleep 5; WAITED=$((WAITED + 5))
  done
  echo "[OK] 서버 준비 완료 (${WAITED}s)"

  python3 -m mtbench_repro.cli generate \
    --questions "$QUESTIONS" \
    --answers-dir "$ANSWERS_DIR" \
    --model-id "$MODEL_ID" \
    --vllm-host localhost \
    --vllm-port "$VLLM_PORT" \
    --temperature 0.7 \
    --max-tokens 1024 \
    --sleep 0.3

  echo "[OK] 생성 완료: $ANSWER_FILE"
  cleanup_server
  echo "[OK] 서버 종료"
done

echo ""
echo "=============================="
echo " 영어 답변 생성 완료"
echo " eval 모델 6개 현황:"
for m in Llama-3.1-8B-Instruct EEVE-Korean-Instruct-10.8B EXAONE-3.5-7.8B-Instruct gemma-2-9b-it Mistral-7B-Instruct-v0.3 Phi-3.5-mini-Instruct; do
  if [ -f "$ANSWERS_DIR/${m}.jsonl" ]; then
    n=$(wc -l < "$ANSWERS_DIR/${m}.jsonl" | tr -d ' ')
    echo "  [OK] $m ($n lines)"
  else
    echo "  [MISS] $m"
  fi
done
echo " 다음 단계: bash scripts/run/a100/run_judge_phase3_a100.sh"
echo " Date: $(date)"
echo "=============================="
