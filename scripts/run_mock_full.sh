#!/bin/bash
# scripts/run_mock_full.sh
#
# 로컬 mock 모드로 전체 파이프라인을 처음부터 끝까지 실행한다.
# (generate → judge-single → judge-pairwise → judge-reference → aggregate)
#
# 기존 결과를 덮어쓰고 새로 실행하려면:
#   bash scripts/run_mock_full.sh
#
# 실행 전제:
#   - PYTHONPATH=src 또는 이 스크립트에서 자동 설정됨
#   - data/mt_bench_questions_sample.jsonl 존재

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

export PYTHONPATH=src

QUESTIONS="data/mt_bench_questions_sample.jsonl"
ANSWERS_DIR="data/mock/answers/"
JUDGMENTS_DIR="data/mock/judgments/"
CSV_OUT="data/mock/results.csv"
MODELS=("vicuna-13b" "llama-13b")

echo "=============================================="
echo " MT-Bench Mock 전체 파이프라인"
echo " 질문파일: $QUESTIONS"
echo " 모델: ${MODELS[*]}"
echo "=============================================="

# ── Step 1: 답변 생성 ──────────────────────────────
echo ""
echo "[Step 1] 답변 생성 (--no-resume: 기존 결과 덮어쓰기)"
for MODEL in "${MODELS[@]}"; do
    python -m mtbench_repro.cli generate \
        --questions "$QUESTIONS" \
        --answers-dir "$ANSWERS_DIR" \
        --model-id "$MODEL" \
        --mock \
        --sleep 0 \
        --no-resume
done
echo "  답변 생성 완료: $(ls $ANSWERS_DIR*.jsonl 2>/dev/null | wc -l)개 파일"

# ── Step 2: Single-answer grading ──────────────────
echo ""
echo "[Step 2] Single-answer grading (Figure 6)"
for MODEL in "${MODELS[@]}"; do
    python -m mtbench_repro.cli judge-single \
        --questions "$QUESTIONS" \
        --answers-dir "$ANSWERS_DIR" \
        --output-dir "$JUDGMENTS_DIR" \
        --model-id "$MODEL" \
        --judge-model gpt-4 \
        --mock \
        --sleep 0 \
        --no-resume
done
echo "  Single grading 완료"

# ── Step 3: Pairwise comparison ─────────────────────
echo ""
echo "[Step 3] Pairwise comparison + AB/BA swap (Figure 5, 9)"
python -m mtbench_repro.cli judge-pairwise \
    --questions "$QUESTIONS" \
    --answers-dir "$ANSWERS_DIR" \
    --output-dir "$JUDGMENTS_DIR" \
    --model-a vicuna-13b \
    --model-b llama-13b \
    --judge-model gpt-4 \
    --mock \
    --sleep 0 \
    --no-resume
echo "  Pairwise 완료"

# ── Step 4: Reference-guided grading ───────────────
echo ""
echo "[Step 4] Reference-guided grading (Figure 10, math/reasoning/coding)"
for MODEL in "${MODELS[@]}"; do
    python -m mtbench_repro.cli judge-reference \
        --questions "$QUESTIONS" \
        --answers-dir "$ANSWERS_DIR" \
        --output-dir "$JUDGMENTS_DIR" \
        --mode single \
        --model-id "$MODEL" \
        --judge-model gpt-4 \
        --mock \
        --sleep 0 \
        --no-resume
done
echo "  Reference-guided 완료"

# ── Step 5: 집계 ────────────────────────────────────
echo ""
echo "[Step 5] 집계 및 Trend 분석"
python -m mtbench_repro.cli aggregate \
    --judgments-dir "$JUDGMENTS_DIR" \
    --questions-path "$QUESTIONS" \
    --output-csv "$CSV_OUT"

echo ""
echo "=============================================="
echo " 완료"
echo " CSV: $CSV_OUT"
echo "=============================================="
