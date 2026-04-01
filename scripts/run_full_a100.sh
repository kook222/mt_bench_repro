#!/bin/bash
# scripts/run_full_a100.sh
# A100 서버 전체 MT-Bench 파이프라인:
#   Step 1: vLLM으로 모델 답변 생성
#   Step 2: GPT-4 judge-single (1-10점 채점)
#   Step 3: GPT-4 judge-pairwise (AB/BA swap)
#   Step 4: GPT-4 judge-reference (math/reasoning/coding)
#   Step 5: 집계 및 Spearman 순위 상관 분석
#
# 사전 요구사항:
#   - OPENAI_API_KEY 환경변수 설정 (judge 단계)
#   - 모델 파일: $HOME_DIR/models/<MODEL_ID>/
#   - 데이터셋: data/mt_bench_questions.jsonl (80문항)
#     → 없으면 먼저 실행: bash scripts/download_dataset.sh
#
# k8s 제출 예시:
#   python3 k8s_create_job.py \
#     -i pytorch/pytorch:2.2.2-cuda12.1-cudnn8-runtime \
#     -g 1 -n "<pod-name>" \
#     -c "cd $HOME && \
#         export OPENAI_API_KEY=sk-xxx && \
#         bash MT_BENCH_REPRO/scripts/run_full_a100.sh > full_run.out 2>&1"

set -e

# ── 경로 및 설정 ──
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
HOME_DIR="$(dirname "$PROJECT_DIR")"
MODEL_DIR="$HOME_DIR/models/Qwen2.5-7B-Instruct"
MODEL_ID="Qwen2.5-7B-Instruct"
JUDGE_MODEL="gpt-4"
QUESTIONS="$PROJECT_DIR/data/mt_bench_questions.jsonl"
ANSWERS_DIR="$PROJECT_DIR/data/answers/"
JUDGMENTS_DIR="$PROJECT_DIR/data/judgments_phase2/"
CSV_OUT="$PROJECT_DIR/data/results.csv"
VLLM_PORT=8000
VLLM_LOG="$HOME_DIR/vllm_server.log"

export HOME="/tmp"
export LOGNAME="$(whoami)"
export USER="$(whoami)"
export PIP_CACHE_DIR="/tmp/pip_cache"
export HF_HOME="/tmp/hf_home"
export TORCHINDUCTOR_CACHE_DIR="/tmp/torchinductor_cache"
export TRITON_CACHE_DIR="/tmp/triton_cache"
export PYTHONPATH="$PROJECT_DIR/src"

echo "=============================="
echo " A100 MT-Bench 전체 파이프라인"
echo " Model: $MODEL_ID"
echo " Judge: $JUDGE_MODEL"
echo " Date:  $(date)"
echo "=============================="

# ── 사전 검증 ──
if [ -z "$OPENAI_API_KEY" ]; then
    echo "[ERROR] OPENAI_API_KEY가 설정되지 않았습니다."
    echo "  export OPENAI_API_KEY=sk-your-key"
    exit 1
fi

if [ ! -f "$QUESTIONS" ] || [ ! -s "$QUESTIONS" ]; then
    echo "[ERROR] 데이터셋 파일이 없거나 비어 있습니다: $QUESTIONS"
    echo "  bash $PROJECT_DIR/scripts/download_dataset.sh"
    exit 1
fi

Q_COUNT=$(wc -l < "$QUESTIONS")
echo "데이터셋: $Q_COUNT 문항 확인"

if [ ! -d "$MODEL_DIR" ]; then
    echo "[ERROR] 모델 디렉토리가 없습니다: $MODEL_DIR"
    echo "  huggingface-cli download Qwen/Qwen2.5-7B-Instruct --local-dir $MODEL_DIR"
    exit 1
fi

# ── Step 1: vLLM 서버 시작 + 답변 생성 ──
echo ""
echo "=============================="
echo " Step 1: 답변 생성 (vLLM)"
echo "=============================="

echo "[Init] 경량 의존성 설치..."
pip install openai tabulate tqdm --target /tmp/site-extra -q
export PYTHONPATH="/tmp/site-extra:$PROJECT_DIR/src"
echo "[Init] 완료."

echo "vLLM 서버 시작 (port=$VLLM_PORT)..."
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

echo "서버 준비 대기 (최대 120초)..."
MAX_WAIT=120
WAITED=0
until curl -s "http://localhost:$VLLM_PORT/health" > /dev/null 2>&1; do
    if [ $WAITED -ge $MAX_WAIT ]; then
        echo "[ERROR] vLLM 서버가 ${MAX_WAIT}초 내에 시작되지 않았습니다."
        tail -30 "$VLLM_LOG"
        kill $VLLM_PID 2>/dev/null || true
        exit 1
    fi
    sleep 5; WAITED=$((WAITED + 5))
    echo "  대기 중... ${WAITED}s"
done
echo "  서버 준비 완료 (${WAITED}s)"

python -m mtbench_repro.cli generate \
    --questions "$QUESTIONS" \
    --answers-dir "$ANSWERS_DIR" \
    --model-id "$MODEL_ID" \
    --vllm-host localhost \
    --vllm-port "$VLLM_PORT" \
    --temperature 0.7 \
    --max-tokens 1024 \
    --sleep 0.5

echo "  답변 생성 완료: $ANSWERS_DIR"

echo "vLLM 서버 종료..."
kill $VLLM_PID 2>/dev/null || true
wait $VLLM_PID 2>/dev/null || true

# ── Step 2: GPT-4 judge-single ──
echo ""
echo "=============================="
echo " Step 2: Single-answer Grading (GPT-4)"
echo "=============================="

python -m mtbench_repro.cli judge-single \
    --questions "$QUESTIONS" \
    --answers-dir "$ANSWERS_DIR" \
    --output-dir "$JUDGMENTS_DIR" \
    --model-id "$MODEL_ID" \
    --judge-model "$JUDGE_MODEL" \
    --openai-api-key "$OPENAI_API_KEY" \
    --sleep 1.0

echo "  Single grading 완료: $JUDGMENTS_DIR/single_grade/"

# ── Step 3: GPT-4 judge-pairwise ──
echo ""
echo "=============================="
echo " Step 3: Pairwise Comparison (GPT-4)"
echo "=============================="
echo "  (비교 대상 모델이 여러 개일 경우 --models 옵션으로 확장 가능)"

# 현재 디렉토리의 모든 모델 목록 자동 감지
AVAILABLE_MODELS=$(python3 -c "
from pathlib import Path
models = [p.stem for p in sorted(Path('$ANSWERS_DIR').glob('*.jsonl'))]
print(' '.join(models))
" 2>/dev/null || echo "")

if [ -z "$AVAILABLE_MODELS" ]; then
    echo "  [SKIP] 답변 파일이 없어 pairwise를 건너뜁니다."
else
    MODEL_COUNT=$(echo "$AVAILABLE_MODELS" | wc -w)
    echo "  감지된 모델: $AVAILABLE_MODELS ($MODEL_COUNT 개)"

    if [ "$MODEL_COUNT" -ge 2 ]; then
        python -m mtbench_repro.cli judge-pairwise \
            --questions "$QUESTIONS" \
            --answers-dir "$ANSWERS_DIR" \
            --output-dir "$JUDGMENTS_DIR" \
            --models $AVAILABLE_MODELS \
            --judge-model "$JUDGE_MODEL" \
            --openai-api-key "$OPENAI_API_KEY" \
            --sleep 2.0
        echo "  Pairwise 완료: $JUDGMENTS_DIR/pairwise/"
    else
        echo "  [SKIP] 모델이 1개뿐이라 pairwise를 건너뜁니다."
    fi
fi

# ── Step 4: GPT-4 judge-reference ──
echo ""
echo "=============================="
echo " Step 4: Reference-guided Grading (GPT-4)"
echo "=============================="
echo "  (math / reasoning / coding 카테고리)"

python -m mtbench_repro.cli judge-reference \
    --questions "$QUESTIONS" \
    --answers-dir "$ANSWERS_DIR" \
    --output-dir "$JUDGMENTS_DIR" \
    --mode single \
    --model-id "$MODEL_ID" \
    --judge-model "$JUDGE_MODEL" \
    --openai-api-key "$OPENAI_API_KEY" \
    --sleep 1.0

echo "  Reference-guided grading 완료: $JUDGMENTS_DIR/single_grade_ref/"

# ── Step 5: 집계 ──
echo ""
echo "=============================="
echo " Step 5: 집계 및 Trend 분석"
echo "=============================="

python -m mtbench_repro.cli aggregate \
    --judgments-dir "$JUDGMENTS_DIR" \
    --output-csv "$CSV_OUT"

echo "  CSV 저장 완료: $CSV_OUT"

echo ""
echo "=============================="
echo " 전체 파이프라인 완료"
echo " $(date)"
echo "=============================="
