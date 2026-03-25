#!/bin/bash
# scripts/run_vllm_qwen_a100.sh
#
# A100 서버에서 Qwen 계열 모델로 전체 MT-Bench 파이프라인을 수행한다.
# (답변 생성 → Judge → 집계)
#
# OpenAI API 키 없이 Qwen2.5-7B-Instruct 하나로 생성 + Judge 역할을 모두 수행.
#
# 실행 전제:
#   - /home/clink-seunghyun/models/Qwen2.5-7B-Instruct 가 존재해야 한다.
#   - pip install vllm transformers openai --break-system-packages 완료 상태
#
# 사용법:
#   # k8s pod으로 제출 (A100 서버 홈 디렉토리에서 실행)
#   python3 k8s_create_job.py \
#     -i pytorch/pytorch:2.2.2-cuda12.1-cudnn8-runtime \
#     -g 1 \
#     -n "clink-seunghyun-1" \
#     -c "cd /home/clink-seunghyun && bash MT_BENCH_REPRO/scripts/run_vllm_qwen_a100.sh > run.out 2>&1"
#
# 주의:
#   - k8s 환경에서 sleep/while true 사용 금지 (규정 위반)
#   - 반드시 작업이 끝나면 프로세스가 종료되어야 한다.

set -e

# ── 경로 설정 ──
HOME_DIR="/home/clink-seunghyun"
PROJECT_DIR="$HOME_DIR/MT_BENCH_REPRO"
MODEL_DIR="$HOME_DIR/models/Qwen2.5-7B-Instruct"
MODEL_ID="Qwen2.5-7B-Instruct"
QUESTIONS="$PROJECT_DIR/data/mt_bench_questions.jsonl"
ANSWERS_DIR="$PROJECT_DIR/data/answers/"
JUDGMENTS_DIR="$PROJECT_DIR/data/judgments/"
OUTPUT_CSV="$PROJECT_DIR/data/results.csv"
VLLM_PORT=8000
VLLM_BASE_URL="http://localhost:$VLLM_PORT/v1"
VLLM_LOG="$HOME_DIR/vllm_server.log"

export PYTHONPATH="$PROJECT_DIR/src"

echo "=============================="
echo " A100 MT-Bench 전체 파이프라인"
echo " Model: $MODEL_ID (생성 + Judge)"
echo " Date: $(date)"
echo "=============================="

# ── Step 1: 의존성 확인 ──
echo "[Step 1] 의존성 확인..."
pip install openai --break-system-packages -q || true
pip install vllm --break-system-packages -q || true

# ── Step 2: 모델 디렉토리 확인 ──
if [ ! -d "$MODEL_DIR" ]; then
    echo "[ERROR] 모델 디렉토리가 없습니다: $MODEL_DIR"
    echo "HuggingFace에서 모델을 먼저 다운로드하세요:"
    echo "  huggingface-cli download Qwen/Qwen2.5-7B-Instruct --local-dir $MODEL_DIR"
    exit 1
fi
echo "[Step 2] 모델 확인 OK: $MODEL_DIR"

# ── Step 3: vLLM 서버 백그라운드 실행 ──
echo "[Step 3] vLLM 서버 시작 (port=$VLLM_PORT)..."
python -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_DIR" \
    --served-model-name "$MODEL_ID" \
    --api-key EMPTY \
    --port "$VLLM_PORT" \
    --max-model-len 4096 \
    --dtype auto \
    --gpu-memory-utilization 0.90 \
    > "$VLLM_LOG" 2>&1 &

VLLM_PID=$!
echo "  vLLM PID: $VLLM_PID"

# ── Step 4: 서버 준비 대기 ──
echo "[Step 4] 서버 준비 대기 (최대 120초)..."
MAX_WAIT=300
WAITED=0
until curl -s "http://localhost:$VLLM_PORT/health" > /dev/null 2>&1; do
    if [ $WAITED -ge $MAX_WAIT ]; then
        echo "[ERROR] vLLM 서버가 ${MAX_WAIT}초 내에 시작되지 않았습니다."
        echo "vLLM 로그:"
        tail -50 "$VLLM_LOG"
        kill $VLLM_PID 2>/dev/null || true
        exit 1
    fi
    sleep 5
    WAITED=$((WAITED + 5))
    echo "  대기 중... ${WAITED}s"
done
echo "  서버 준비 완료 (${WAITED}s)"

# ── Step 5: 답변 생성 ──
echo "[Step 5] 답변 생성 시작..."
python -m mtbench_repro.cli generate \
    --questions "$QUESTIONS" \
    --answers-dir "$ANSWERS_DIR" \
    --model-id "$MODEL_ID" \
    --vllm-host localhost \
    --vllm-port "$VLLM_PORT" \
    --temperature 0.7 \
    --max-tokens 1024 \
    --sleep 0.5

echo "[Step 5] 답변 생성 완료."
echo "결과 파일: $ANSWERS_DIR/${MODEL_ID}.jsonl"

# ── Step 6: Single-answer grading (Qwen이 Judge 역할) ──
echo ""
echo "[Step 6] Single-answer grading 시작 (Figure 6)..."
python -m mtbench_repro.cli judge-single \
    --questions "$QUESTIONS" \
    --answers-dir "$ANSWERS_DIR" \
    --output-dir "$JUDGMENTS_DIR" \
    --model-id "$MODEL_ID" \
    --judge-model "$MODEL_ID" \
    --openai-base-url "$VLLM_BASE_URL" \
    --openai-api-key EMPTY \
    --sleep 0.3
echo "[Step 6] Single-answer grading 완료."

# ── Step 7: Reference-guided grading (math / reasoning / coding) ──
echo ""
echo "[Step 7] Reference-guided grading 시작 (Figure 10, math/reasoning/coding)..."
python -m mtbench_repro.cli judge-reference \
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

# ── Step 8: Pairwise comparison (Figure 5, 9) ──
# 논문 재현에 pairwise win rate (Figure 3, 5, 9)가 필요하므로 반드시 실행.
# Qwen 단일 모델로는 모델 간 비교가 안 되므로, self-comparison을 건너뛰고
# 대신 answers/ 디렉토리에 여러 모델이 있을 경우에만 실행한다.
echo ""
echo "[Step 8] Pairwise comparison 확인..."
AVAILABLE_MODELS=$(ls "$ANSWERS_DIR"*.jsonl 2>/dev/null | wc -l)
if [ "$AVAILABLE_MODELS" -ge 2 ]; then
    echo "  답변 파일 ${AVAILABLE_MODELS}개 감지 → pairwise 실행"
    python -m mtbench_repro.cli judge-pairwise \
        --questions "$QUESTIONS" \
        --answers-dir "$ANSWERS_DIR" \
        --output-dir "$JUDGMENTS_DIR" \
        --models $(ls "$ANSWERS_DIR"*.jsonl | xargs -I{} basename {} .jsonl | tr '\n' ' ') \
        --judge-model "$MODEL_ID" \
        --openai-base-url "$VLLM_BASE_URL" \
        --openai-api-key EMPTY \
        --sleep 0.5
    echo "[Step 8] Pairwise 완료."
else
    echo "  답변 파일이 1개뿐 → pairwise skip (모델 추가 후 재실행 가능)"
fi

# ── Step 9: 집계 및 CSV 저장 ──
echo ""
echo "[Step 9] 결과 집계 및 Trend 분석..."
python -m mtbench_repro.cli aggregate \
    --judgments-dir "$JUDGMENTS_DIR" \
    --output-csv "$OUTPUT_CSV"
echo "[Step 9] 집계 완료. CSV: $OUTPUT_CSV"

# ── Step 10: vLLM 서버 종료 ──
echo ""
echo "[Step 10] vLLM 서버 종료..."
kill $VLLM_PID 2>/dev/null || true
wait $VLLM_PID 2>/dev/null || true
echo "  서버 종료 완료."

# ── 최종 요약 ──
echo ""
echo "=============================="
echo " 전체 파이프라인 완료"
echo " 답변: $ANSWERS_DIR/${MODEL_ID}.jsonl"
echo " 점수: $OUTPUT_CSV"
echo " 날짜: $(date)"
echo "=============================="