#!/bin/bash
# scripts/run_judge_pairwise_local.sh
# 로컬 mock으로 pairwise comparison을 수행한다.
# 논문 Figure 5, 9: AB/BA swap으로 position bias를 완화한 conservative winner 판정.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

export PYTHONPATH=src

QUESTIONS="data/mt_bench_questions_sample.jsonl"
ANSWERS_DIR="data/answers/"
OUTPUT_DIR="data/judgments_phase2/"

echo "=============================="
echo " Step 3: Pairwise Comparison"
echo "=============================="

echo ""
echo "[judge-pairwise] vicuna-13b vs llama-13b"
python -m mtbench_repro.cli judge-pairwise \
    --questions "$QUESTIONS" \
    --answers-dir "$ANSWERS_DIR" \
    --output-dir "$OUTPUT_DIR" \
    --model-a vicuna-13b \
    --model-b llama-13b \
    --judge-model gpt-4 \
    --mock \
    --sleep 0

echo ""
echo "pairwise 판정 완료. 결과 확인:"
ls -lh "$OUTPUT_DIR/pairwise/" 2>/dev/null || echo "(pairwise/ 없음)"

echo ""
echo "판정 샘플 (winner / AB / BA):"
for f in "$OUTPUT_DIR"/pairwise/*.jsonl; do
    [ -f "$f" ] || continue
    echo "  $f:"
    python3 -c "
import json
for line in open('$f'):
    d = json.loads(line)
    print(f'    qid={d[\"question_id\"]:3d}  winner={d[\"winner\"]:15s}  ab={d[\"winner_ab\"]}  ba={d[\"winner_ba\"]}')
"
done
