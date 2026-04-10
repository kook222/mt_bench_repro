#!/bin/bash
# scripts/run/local/run_judge_reference_local.sh
# 로컬 mock으로 reference-guided grading을 수행한다.
# 논문 Section 3.4, Figure 8, 10:
#   - reference-guided single: math/reasoning/coding 카테고리 대상
#   - reference-guided pairwise: 동일 카테고리 pairwise + swap

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_ROOT"

export PYTHONPATH=src

QUESTIONS="data/mt_bench_questions_sample.jsonl"
ANSWERS_DIR="data/mock/answers/"
OUTPUT_DIR="data/mock/judgments/"

echo "=============================="
echo " Step 3.5: Reference-guided Grading"
echo "=============================="
echo " 대상: math, reasoning, coding 카테고리"
echo " (논문 Section 3.4 — reference 제공 시 실패율 70% → 15%)"
echo ""

# --- Single reference grading ---
echo "--- [judge-reference single] ---"
for MODEL in "vicuna-13b" "llama-13b"; do
    echo ""
    echo "[judge-reference single] model=$MODEL"
    python -m mtbench_repro.cli judge-reference \
        --questions "$QUESTIONS" \
        --answers-dir "$ANSWERS_DIR" \
        --output-dir "$OUTPUT_DIR" \
        --mode single \
        --model-id "$MODEL" \
        --judge-model gpt-4 \
        --mock \
        --sleep 0
done

echo ""
echo "결과 확인 (single_grade_ref/):"
ls -lh "$OUTPUT_DIR/single_grade_ref/" 2>/dev/null || echo "(single_grade_ref/ 없음 — 해당 카테고리 문항 없으면 정상)"

# --- Pairwise reference grading ---
echo ""
echo "--- [judge-reference pairwise] ---"
echo ""
echo "[judge-reference pairwise] vicuna-13b vs llama-13b"
python -m mtbench_repro.cli judge-reference \
    --questions "$QUESTIONS" \
    --answers-dir "$ANSWERS_DIR" \
    --output-dir "$OUTPUT_DIR" \
    --mode pairwise \
    --model-a vicuna-13b \
    --model-b llama-13b \
    --judge-model gpt-4 \
    --mock \
    --sleep 0

echo ""
echo "결과 확인 (pairwise_ref/):"
ls -lh "$OUTPUT_DIR/pairwise_ref/" 2>/dev/null || echo "(pairwise_ref/ 없음 — 해당 카테고리 문항 없으면 정상)"

echo ""
echo "Reference-guided grading 완료."
