#!/bin/bash
# scripts/run_judge_single_local.sh
# 로컬 mock으로 single-answer grading을 수행한다.
# 실행: bash scripts/run_judge_single_local.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

export PYTHONPATH=src

QUESTIONS="data/mt_bench_questions_sample.jsonl"
ANSWERS_DIR="data/answers/"
OUTPUT_DIR="data/judgments_phase2/"

echo "=============================="
echo " Step 2: Single-answer Grading"
echo "=============================="

for MODEL in "vicuna-13b" "llama-13b"; do
    echo ""
    echo "[judge-single] model=$MODEL"
    python -m mtbench_repro.cli judge-single \
        --questions "$QUESTIONS" \
        --answers-dir "$ANSWERS_DIR" \
        --output-dir "$OUTPUT_DIR" \
        --model-id "$MODEL" \
        --judge-model gpt-4 \
        --mock \
        --sleep 0
done

echo ""
echo "채점 완료. 결과 확인:"
ls -lh "$OUTPUT_DIR/single_grade/" 2>/dev/null || echo "(single_grade/ 없음)"

echo ""
echo "점수 샘플:"
for f in "$OUTPUT_DIR"/single_grade/*.jsonl; do
    [ -f "$f" ] || continue
    echo "  $f:"
    python3 -c "
import json, sys
for line in open('$f'):
    d = json.loads(line)
    print(f'    qid={d[\"question_id\"]:3d}  s1={d[\"score_turn1\"]}  s2={d[\"score_turn2\"]}  avg={d.get(\"avg_score\", \"N/A\")}')
"
done