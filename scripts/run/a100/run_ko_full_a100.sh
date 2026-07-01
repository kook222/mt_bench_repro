#!/bin/bash
# scripts/run/a100/run_ko_full_a100.sh
#
# KO 전체 파이프라인 순차 실행:
#   1. 답변 생성 (6개 eval 모델)
#   2. Qwen judge (7B / 14B / 32B)
#   3. EXAONE-32B judge
#
# 사용법 (서버에서):
#   python3 k8s_create_job.py \
#     -i vllm/vllm-openai:v0.6.6 \
#     -g 1 \
#     -n "<job-name>" \
#     -c "cd /path/to/MT_BENCH_REPRO && bash scripts/run/a100/run_ko_full_a100.sh > /tmp/run_ko_full.log 2>&1 && echo DONE"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=============================================="
echo " KO 전체 파이프라인 시작"
echo " Date: $(date)"
echo "=============================================="

# Step 1: 답변 생성
echo ""
echo "[STEP 1/3] 한국어 답변 생성 시작..."
bash "$SCRIPT_DIR/run_generate_ko_a100.sh"
echo "[STEP 1/3] 완료. Date: $(date)"

# Step 2: Qwen judge
echo ""
echo "[STEP 2/3] Qwen judge 시작..."
bash "$SCRIPT_DIR/run_judge_ko_a100.sh"
echo "[STEP 2/3] 완료. Date: $(date)"

# Step 3: EXAONE judge
echo ""
echo "[STEP 3/3] EXAONE-32B judge 시작..."
bash "$SCRIPT_DIR/run_judge_exaone32b_a100.sh"
echo "[STEP 3/3] 완료. Date: $(date)"

echo ""
echo "=============================================="
echo " KO 전체 파이프라인 완료"
echo " Date: $(date)"
echo "=============================================="
