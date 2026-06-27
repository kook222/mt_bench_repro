#!/bin/bash
# scripts/run/a100/run_generate_ko_a100.sh
#
# Phase 1 (한국어): eval 모델 6개로 한국어 MT-Bench 답변 생성.
#
# 영어 실험과 동일한 6개 eval 모델:
#   Llama-3.1-8B-Instruct
#   EEVE-Korean-Instruct-10.8B   ← 한국어 특화 (SOLAR 대체, SOLAR 기반 fine-tune)
#   EXAONE-3.5-7.8B-Instruct     ← 한국어 특화 (LG AI Research)
#   gemma-2-9b-it
#   Mistral-7B-Instruct-v0.3
#   Phi-3.5-mini-Instruct
#
# 영어와의 차이:
#   - 질문 파일: data/ko/questions.jsonl (한국어 번역본)
#   - 답변 저장: data/ko/answers/
#   - 전 모델 새로 생성 (영어 answers 재사용 불가)
#   - system prompt: "반드시 한국어로 답하세요."
#
# EEVE-Korean: SOLAR와 동일한 ### User/Assistant 템플릿 → solar_chat_template.jinja 재사용
#
# 전제:
#   - 모든 모델이 MODEL_BASE_DIR에 다운로드되어 있어야 함.
#   - data/ko/questions.jsonl이 존재해야 함.

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
QUESTIONS="$PROJECT_DIR/data/ko/questions.jsonl"
ANSWERS_DIR="$PROJECT_DIR/data/ko/answers/"
VLLM_PORT=8000
VLLM_LOG="/tmp/vllm_generate_ko.log"
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

# ── 질문 파일 확인 ────────────────────────────────────────────────────────────
if [ ! -f "$QUESTIONS" ]; then
  echo "[ERROR] 한국어 질문 파일 없음: $QUESTIONS"
  echo "        Phase 0 완료 후 실행하세요 (data/ko/questions.jsonl 필요)."
  exit 1
fi
echo "[OK] 질문 파일: $QUESTIONS ($(wc -l < "$QUESTIONS")문항)"

# ── 출력 디렉토리 생성 ────────────────────────────────────────────────────────
mkdir -p "$ANSWERS_DIR"

# ── eval 모델 목록 ────────────────────────────────────────────────────────────
# 형식: "모델_ID:HF_ID:max-model-len:gpu-util:chat_template"
# chat_template: "solar" = solar_chat_template.jinja, "default" = vLLM 자동
# EEVE-Korean: SOLAR 기반 fine-tune → 동일한 ### User/Assistant 포맷 사용
declare -a MODEL_LIST=(
  "Llama-3.1-8B-Instruct:meta-llama/Llama-3.1-8B-Instruct:4096:0.90:default"
  "EEVE-Korean-Instruct-10.8B:yanolja/EEVE-Korean-Instruct-10.8B-v1.0:4096:0.90:solar"
  "EXAONE-3.5-7.8B-Instruct:LGAI-MEDIUS/EXAONE-3.5-7.8B-Instruct:4096:0.90:default"
  "gemma-2-9b-it:google/gemma-2-9b-it:4096:0.90:default"
  "Mistral-7B-Instruct-v0.3:mistralai/Mistral-7B-Instruct-v0.3:4096:0.90:default"
  "Phi-3.5-mini-Instruct:microsoft/Phi-3.5-mini-instruct:4096:0.90:default"
)

SOLAR_TEMPLATE="$SCRIPT_DIR/solar_chat_template.jinja"

echo "=============================="
echo " 한국어 MT-Bench 답변 생성"
echo " 총 ${#MODEL_LIST[@]}개 eval 모델"
echo " 질문: $QUESTIONS"
echo " 저장: $ANSWERS_DIR"
echo " Date: $(date)"
echo "=============================="

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

  # 모델 디렉토리 확인
  if [ ! -d "$MODEL_DIR" ]; then
    echo "[ERROR] 모델 디렉토리 없음: $MODEL_DIR"
    echo "        huggingface-cli download $HF_ID --local-dir $MODEL_DIR"
    exit 1
  fi

  # resume 안내
  if [ -f "$ANSWER_FILE" ]; then
    EXISTING=$(wc -l < "$ANSWER_FILE" | tr -d ' ')
    echo "[INFO] 기존 답변 $EXISTING줄 발견 — resume 모드로 실행."
  fi

  # vLLM 서버 시작
  echo "[Start] vLLM 서버 시작..."
  # EEVE-Korean: SOLAR와 동일한 ### User/Assistant 포맷 → solar_chat_template.jinja 재사용
  CHAT_TEMPLATE_ARG=""
  if [ "$TMPL" = "solar" ]; then
    CHAT_TEMPLATE_ARG="--chat-template $SOLAR_TEMPLATE"
    echo "[INFO] solar chat template 적용: $SOLAR_TEMPLATE"
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

  # 서버 준비 대기
  MAX_WAIT=600
  WAITED=0
  until curl -s "http://localhost:$VLLM_PORT/health" > /dev/null 2>&1; do
    if [ "$WAITED" -ge "$MAX_WAIT" ]; then
      echo "[ERROR] vLLM 서버가 ${MAX_WAIT}초 내에 시작되지 않음."
      tail -20 "$VLLM_LOG"
      exit 1
    fi
    sleep 5
    WAITED=$((WAITED + 5))
  done
  echo "[OK] 서버 준비 완료 (${WAITED}s)"

  # 답변 생성 (한국어 system prompt 항상 적용)
  python3 -m mtbench_repro.cli generate \
    --questions "$QUESTIONS" \
    --answers-dir "$ANSWERS_DIR" \
    --model-id "$MODEL_ID" \
    --vllm-host localhost \
    --vllm-port "$VLLM_PORT" \
    --temperature 0.7 \
    --max-tokens 1024 \
    --sleep 0.3 \
    --system-prompt "반드시 한국어로 답하세요."

  echo "[OK] 생성 완료: $ANSWER_FILE"

  # 서버 종료
  cleanup_server
  echo "[OK] 서버 종료"

done

echo ""
echo "=============================="
echo " 한국어 답변 생성 전체 완료"
echo " 결과:"
for ENTRY in "${MODEL_LIST[@]}"; do
  MODEL_ID="${ENTRY%%:*}"
  F="$ANSWERS_DIR/${MODEL_ID}.jsonl"
  if [ -f "$F" ]; then
    echo "  [OK] $MODEL_ID ($(wc -l < "$F")줄)"
  else
    echo "  [MISS] $MODEL_ID"
  fi
done
echo ""
echo " 다음 단계: bash scripts/run/a100/run_judge_ko_a100.sh"
echo " Date: $(date)"
echo "=============================="
