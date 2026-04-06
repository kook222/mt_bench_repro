#!/bin/bash
# scripts/run_generate_local.sh
# 로컬 mock으로 두 모델의 답변을 생성한다.
# 실행: bash scripts/run_generate_local.sh

set -e  # 오류 발생 시 즉시 중단

# 프로젝트 루트에서 실행해야 한다
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

export PYTHONPATH=src

QUESTIONS="data/mt_bench_questions_sample.jsonl"
ANSWERS_DIR="data/mock/answers/"

echo "=============================="
echo " Step 1: Mock 답변 생성"
echo "=============================="

for MODEL in "vicuna-13b" "llama-13b"; do
    echo ""
    echo "[generate] model=$MODEL"
    python -m mtbench_repro.cli generate \
        --questions "$QUESTIONS" \
        --answers-dir "$ANSWERS_DIR" \
        --model-id "$MODEL" \
        --mock \
        --sleep 0
done

echo ""
echo "생성 완료. 결과 확인:"
ls -lh "$ANSWERS_DIR"
