#!/bin/bash
# scripts/run/local/run_aggregate_local.sh
# 판정 결과를 집계하고 trend를 분석한다.
# 실행: bash scripts/run/local/run_aggregate_local.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_ROOT"

export PYTHONPATH=src

# mock 파이프라인 결과 집계용 (run_mock_full.sh 이후 실행)
OUTPUT_DIR="data/mock/judgments/"
CSV_OUT="data/mock/results.csv"

echo "=============================="
echo " 집계 (mock)"
echo "=============================="

python -m mtbench_repro.cli aggregate \
    --judgments-dir "$OUTPUT_DIR" \
    --questions-path "data/en/questions.jsonl" \
    --output-csv "$CSV_OUT"

echo ""
echo "CSV 저장 완료: $CSV_OUT"
[ -f "$CSV_OUT" ] && cat "$CSV_OUT"
