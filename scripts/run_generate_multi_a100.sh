#!/bin/bash
# scripts/run_generate_multi_a100.sh
#
# A100에서 여러 모델의 답변을 순차적으로 생성한다.
# 각 모델마다 vLLM 서버를 올리고 → generate → 서버 종료 순으로 반복.
#
# 사용법 (k8s job 내부에서 호출):
#   bash scripts/run_generate_multi_a100.sh
#
# 전제:
#   - 아래 MODEL_LIST에 지정된 모델이 MODEL_BASE_DIR에 이미 다운로드되어 있어야 한다.
#   - vLLM, openai 패키지가 설치되어 있어야 한다.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

HOME_DIR="$(dirname "$PROJECT_DIR")"
export PYTHONPATH="$PROJECT_DIR/src"
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
VLLM_LOG="$HOME_DIR/vllm_generate.log"

# ── 경량 의존성 설치 (vllm/vllm-openai 이미지 전용) ──────────────────────
echo "[Init] 경량 의존성 설치..."
pip install openai tabulate tqdm --target /tmp/site-extra -q
export PYTHONPATH="/tmp/site-extra:$PROJECT_DIR/src"
echo "[Init] 완료."

# ── 생성할 모델 목록 ──────────────────────────────────────────────────────
# 형식: "HuggingFace_ID:served-model-name"
# served-model-name은 답변 파일명과 CLI --model-id에 그대로 쓰인다.
MODEL_LIST=(
  "Qwen/Qwen2.5-7B-Instruct:Qwen2.5-7B-Instruct"
  "upstage/SOLAR-10.7B-Instruct-v1.0:SOLAR-10.7B-Instruct"
  "mistralai/Mistral-7B-Instruct-v0.3:Mistral-7B-Instruct-v0.3"
  "google/gemma-2-9b-it:gemma-2-9b-it"
  "01-ai/Yi-1.5-9B-Chat:Yi-1.5-9B-Chat"
  "microsoft/Phi-3.5-mini-instruct:Phi-3.5-mini-Instruct"
)

echo "=============================="
echo " Multi-model Generation"
echo " 모델 수: ${#MODEL_LIST[@]}"
echo " Date: $(date)"
echo "=============================="

for ENTRY in "${MODEL_LIST[@]}"; do
  HF_ID="${ENTRY%%:*}"
  MODEL_ID="${ENTRY##*:}"
  MODEL_DIR="$MODEL_BASE_DIR/$MODEL_ID"

  echo ""
  echo "──────────────────────────────"
  echo " 모델: $MODEL_ID"
  echo "──────────────────────────────"

  # 모델 디렉토리 확인
  if [ ! -d "$MODEL_DIR" ]; then
    echo "[SKIP] 모델 디렉토리 없음: $MODEL_DIR"
    echo "       먼저 다운로드: huggingface-cli download $HF_ID --local-dir $MODEL_DIR"
    continue
  fi

  # 이미 생성된 경우 skip (resume 지원)
  ANSWER_FILE="$ANSWERS_DIR/${MODEL_ID}.jsonl"
  if [ -f "$ANSWER_FILE" ]; then
    EXISTING=$(wc -l < "$ANSWER_FILE" | tr -d ' ')
    echo "[INFO] 기존 답변 파일 발견: $EXISTING 줄. resume 모드로 실행."
  fi

  # vLLM 서버 시작
  vllm serve "$MODEL_DIR" \
    --served-model-name "$MODEL_ID" \
    --api-key EMPTY \
    --port "$VLLM_PORT" \
    --max-model-len 4096 \
    --dtype auto \
    --gpu-memory-utilization 0.90 \
    > "$VLLM_LOG" 2>&1 &
  VLLM_PID=$!

  # 서버 준비 대기 (최대 300초)
  MAX_WAIT=300
  WAITED=0
  until curl -s "http://localhost:$VLLM_PORT/health" > /dev/null 2>&1; do
    if [ "$WAITED" -ge "$MAX_WAIT" ]; then
      echo "[ERROR] vLLM 서버가 ${MAX_WAIT}초 내에 시작되지 않음."
      tail -20 "$VLLM_LOG"
      kill "$VLLM_PID" 2>/dev/null || true
      exit 1
    fi
    sleep 5
    WAITED=$((WAITED + 5))
  done
  echo "[OK] 서버 준비 완료 (${WAITED}s)"

  # 답변 생성
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

  # vLLM 서버 종료
  kill "$VLLM_PID" 2>/dev/null || true
  wait "$VLLM_PID" 2>/dev/null || true
  echo "[OK] 서버 종료"
done

echo ""
echo "=============================="
echo " 전체 생성 완료"
echo " 파일 목록:"
ls -lh "$ANSWERS_DIR"*.jsonl 2>/dev/null || echo " (없음)"
echo "=============================="
