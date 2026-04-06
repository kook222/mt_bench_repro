#!/bin/bash
# scripts/run_vllm_qwen_a100.sh
#
# A100 서버에서 Qwen2.5-7B-Instruct로 전체 MT-Bench 파이프라인을 수행한다.
# (답변 생성 → Judge → 집계)
#
# OpenAI API 키 없이 Qwen2.5-7B-Instruct 하나로 생성 + Judge 역할을 모두 수행.
#
# 실행 전제:
#   - $HOME/models/Qwen2.5-7B-Instruct 가 존재해야 한다.
#   - 이미지: vllm/vllm-openai:v0.6.6 (vLLM + PyTorch + transformers 사전 설치됨)
#
# 사용법:
#   python3 k8s_create_job.py \
#     -i vllm/vllm-openai:v0.6.6 \
#     -g 1 \
#     -n "<pod-name>" \
#     -c "cd $HOME && bash MT_BENCH_REPRO/scripts/run_vllm_qwen_a100.sh > run.out 2>&1"
#
# 주의:
#   - k8s 환경에서 작업이 끝나면 반드시 프로세스가 종료되어야 한다.

set -e

# ── 경로 설정 ──────────────────────────────────────────────────────────────
HOME_DIR="$HOME"
PROJECT_DIR="$HOME_DIR/MT_BENCH_REPRO"
MODEL_DIR="$HOME_DIR/models/Qwen2.5-7B-Instruct"
MODEL_ID="Qwen2.5-7B-Instruct"
QUESTIONS="$PROJECT_DIR/data/mt_bench_questions.jsonl"
ANSWERS_DIR="$PROJECT_DIR/data/answers/"
JUDGMENTS_DIR="$PROJECT_DIR/data/judgments_phase2/"
OUTPUT_CSV="$PROJECT_DIR/data/results.csv"
VLLM_PORT=8000
VLLM_BASE_URL="http://localhost:$VLLM_PORT/v1"
VLLM_LOG="/tmp/vllm.log"
EXTRA_PKGS="/tmp/site-extra"

# k8s 컨테이너 안에서 writable 경로 강제 지정
# (UID가 /etc/passwd에 없는 환경에서 getpass.getuser() 실패 방지)
export HOME="/tmp"
export LOGNAME="$(whoami)"
export USER="$(whoami)"
export PIP_CACHE_DIR="/tmp/pip_cache"
export HF_HOME="/tmp/hf_home"
export TORCHINDUCTOR_CACHE_DIR="/tmp/torchinductor_cache"
export TRITON_CACHE_DIR="/tmp/triton_cache"
# vllm 이미지의 시스템 패키지 + 우리 경량 패키지 + 프로젝트 코드
export PYTHONPATH="$EXTRA_PKGS:$PROJECT_DIR/src"

echo "=============================="
echo " A100 MT-Bench 전체 파이프라인"
echo " Model: $MODEL_ID (생성 + Judge)"
echo " Date: $(date)"
echo "=============================="

# ── 환경 진단 ─────────────────────────────────────────────────────────────
echo "[Diag] python3: $(which python3 2>/dev/null || echo NOT_FOUND)"
echo "[Diag] vllm  : $(python3 -c 'import vllm; print(vllm.__version__)' 2>&1)"
echo "[Diag] vllm cmd: $(which vllm 2>/dev/null || echo NOT_FOUND)"

# ── Step 1: 경량 의존성 설치 ──────────────────────────────────────────────
# vllm/vllm-openai 이미지에는 vLLM, PyTorch, transformers가 이미 설치됨.
# venv 없이 --target으로 경량 패키지만 별도 경로에 설치 → 시스템 Python 그대로 사용.
echo ""
echo "[Step 1] 경량 의존성 설치 (openai, tabulate, tqdm)..."
pip install openai tabulate tqdm --target "$EXTRA_PKGS" -q
echo "[Step 1] 의존성 설치 완료."

# ── Step 2: 모델 디렉토리 확인 ────────────────────────────────────────────
echo ""
echo "[Step 2] 모델 디렉토리 확인..."
if [ ! -d "$MODEL_DIR" ]; then
    echo "[ERROR] 모델 디렉토리가 없습니다: $MODEL_DIR"
    echo "  huggingface-cli download Qwen/Qwen2.5-7B-Instruct --local-dir $MODEL_DIR"
    exit 1
fi
echo "[Step 2] 모델 확인 OK: $MODEL_DIR"

# ── Step 3: vLLM 서버 백그라운드 실행 ────────────────────────────────────
# vllm/vllm-openai 이미지: `vllm serve` CLI 사용 (image 내장 launcher)
echo ""
echo "[Step 3] vLLM 서버 시작 (port=$VLLM_PORT)..."
vllm serve "$MODEL_DIR" \
    --served-model-name "$MODEL_ID" \
    --api-key EMPTY \
    --port "$VLLM_PORT" \
    --max-model-len 4096 \
    --dtype auto \
    --gpu-memory-utilization 0.90 \
    > "$VLLM_LOG" 2>&1 &

VLLM_PID=$!
echo "  vLLM PID: $VLLM_PID"

# ── Step 4: 서버 준비 대기 ────────────────────────────────────────────────
echo ""
echo "[Step 4] 서버 준비 대기 (최대 300초)..."
MAX_WAIT=300
WAITED=0
until curl -s "http://localhost:$VLLM_PORT/health" > /dev/null 2>&1; do
    if ! kill -0 "$VLLM_PID" 2>/dev/null; then
        echo "[ERROR] vLLM 프로세스가 예기치 않게 종료되었습니다."
        echo "=== vLLM 로그 (마지막 50줄) ==="
        tail -50 "$VLLM_LOG"
        exit 1
    fi
    if [ "$WAITED" -ge "$MAX_WAIT" ]; then
        echo "[ERROR] vLLM 서버가 ${MAX_WAIT}초 내에 응답하지 않았습니다."
        echo "=== vLLM 로그 (마지막 50줄) ==="
        tail -50 "$VLLM_LOG"
        kill "$VLLM_PID" 2>/dev/null || true
        exit 1
    fi
    sleep 5
    WAITED=$((WAITED + 5))
    echo "  대기 중... ${WAITED}s"
done
echo "[Step 4] 서버 준비 완료 (${WAITED}s)"

# ── Step 5: 답변 생성 ─────────────────────────────────────────────────────
echo ""
echo "[Step 5] 답변 생성 시작..."
python3 -m mtbench_repro.cli generate \
    --questions "$QUESTIONS" \
    --answers-dir "$ANSWERS_DIR" \
    --model-id "$MODEL_ID" \
    --vllm-host localhost \
    --vllm-port "$VLLM_PORT" \
    --temperature 0.7 \
    --max-tokens 1024 \
    --sleep 0.5
echo "[Step 5] 답변 생성 완료: $ANSWERS_DIR${MODEL_ID}.jsonl"

# ── Step 6: Single-answer grading ────────────────────────────────────────
echo ""
echo "[Step 6] Single-answer grading 시작..."
python3 -m mtbench_repro.cli judge-single \
    --questions "$QUESTIONS" \
    --answers-dir "$ANSWERS_DIR" \
    --output-dir "$JUDGMENTS_DIR" \
    --model-id "$MODEL_ID" \
    --judge-model "$MODEL_ID" \
    --openai-base-url "$VLLM_BASE_URL" \
    --openai-api-key EMPTY \
    --sleep 0.3
echo "[Step 6] Single-answer grading 완료."

# ── Step 7: Reference-guided grading (math / reasoning / coding) ─────────
echo ""
echo "[Step 7] Reference-guided grading 시작 (math/reasoning/coding)..."
python3 -m mtbench_repro.cli judge-reference \
    --questions "$QUESTIONS" \
    --answers-dir "$ANSWERS_DIR" \
    --output-dir "$JUDGMENTS_DIR" \
    --mode single \
    --model-id "$MODEL_ID" \
    --judge-model "$MODEL_ID" \
    --openai-base-url "$VLLM_BASE_URL" \
    --openai-api-key EMPTY \
    --sleep 0.3
echo "[Step 7] Reference-guided grading 완료."

# ── Step 8: Pairwise comparison (answers/ 에 모델이 2개 이상일 때만) ──────
echo ""
echo "[Step 8] Pairwise comparison 확인..."
AVAILABLE_MODELS=$(ls "$ANSWERS_DIR"*.jsonl 2>/dev/null | wc -l)
if [ "$AVAILABLE_MODELS" -ge 2 ]; then
    echo "  답변 파일 ${AVAILABLE_MODELS}개 감지 → pairwise 실행"
    MODEL_NAMES=()
    while IFS= read -r f; do
        MODEL_NAMES+=("$(basename "$f" .jsonl)")
    done < <(ls "$ANSWERS_DIR"*.jsonl)
    python3 -m mtbench_repro.cli judge-pairwise \
        --questions "$QUESTIONS" \
        --answers-dir "$ANSWERS_DIR" \
        --output-dir "$JUDGMENTS_DIR" \
        --models "${MODEL_NAMES[@]}" \
        --judge-model "$MODEL_ID" \
        --openai-base-url "$VLLM_BASE_URL" \
        --openai-api-key EMPTY \
        --sleep 0.5
    echo "[Step 8] Pairwise 완료."
else
    echo "  답변 파일 1개 → pairwise skip"
fi

# ── Step 9: 집계 ──────────────────────────────────────────────────────────
echo ""
echo "[Step 9] 결과 집계 및 Trend 분석..."
python3 -m mtbench_repro.cli aggregate \
    --judgments-dir "$JUDGMENTS_DIR" \
    --questions-path "$QUESTIONS" \
    --output-csv "$OUTPUT_CSV"
echo "[Step 9] 집계 완료. CSV: $OUTPUT_CSV"

# ── Step 10: vLLM 서버 종료 ───────────────────────────────────────────────
echo ""
echo "[Step 10] vLLM 서버 종료..."
kill "$VLLM_PID" 2>/dev/null || true
wait "$VLLM_PID" 2>/dev/null || true
echo "  서버 종료 완료."

# ── 최종 요약 ─────────────────────────────────────────────────────────────
echo ""
echo "=============================="
echo " 전체 파이프라인 완료"
echo " 답변: $ANSWERS_DIR${MODEL_ID}.jsonl"
echo " 점수: $OUTPUT_CSV"
echo " 날짜: $(date)"
echo "=============================="
