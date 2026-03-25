#!/bin/bash
# scripts/run_aggregate_local.sh
# 판정 결과를 집계하고 trend를 분석한다.
# 실행: bash scripts/run_aggregate_local.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

export PYTHONPATH=src

OUTPUT_DIR="data/judgments/"
CSV_OUT="data/results.csv"

echo "=============================="
echo " Step 4: 집계 및 Trend 분석"
echo "=============================="

python -m mtbench_repro.cli aggregate \
    --judgments-dir "$OUTPUT_DIR" \
    --output-csv "$CSV_OUT"

echo ""
echo "CSV 저장 완료: $CSV_OUT"
[ -f "$CSV_OUT" ] && cat "$CSV_OUT"