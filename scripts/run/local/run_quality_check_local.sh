#!/bin/bash
# scripts/run/local/run_quality_check_local.sh
#
# 한국어 번역 품질 검증 (로컬 실행)
#
# 실행 순서:
#   1. back_translate.py   : KO → EN 역번역 (GPT-4o-mini)
#   2. analyze_translation_validity.py : 3차원 점수 채점 (GPT-4o-mini)
#
# 필수 환경 변수:
#   export OPENAI_API_KEY="sk-..."
#
# 출력 파일:
#   data/ko/questions_back.jsonl
#   data/ko/results/results_translation_validity.csv
#   data/ko/results/results_translation_validity_per_category.csv
#
# 사용법:
#   export OPENAI_API_KEY="sk-..."
#   bash scripts/run/local/run_quality_check_local.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_DIR"

export PYTHONPATH="$PROJECT_DIR/src"

echo "=============================="
echo " 번역 품질 검증 (로컬)"
echo " Date: $(date)"
echo "=============================="

# API 키 확인
if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "[ERROR] OPENAI_API_KEY가 설정되지 않았습니다."
  echo "        export OPENAI_API_KEY=\"sk-...\""
  exit 1
fi
echo "[OK] OPENAI_API_KEY 확인됨"

# 입력 파일 확인
if [ ! -f "data/ko/questions.jsonl" ]; then
  echo "[ERROR] 한국어 질문 파일 없음: data/ko/questions.jsonl"
  exit 1
fi
echo "[OK] 입력 파일 확인됨 (data/ko/questions.jsonl)"

mkdir -p data/ko/results

# ── Step 1: 역번역 ────────────────────────────────────────────────────────────
echo ""
echo "[Step 1/2] 역번역 생성 (KO → EN)..."
echo "  출력: data/ko/questions_back.jsonl"

if [ -f "data/ko/questions_back.jsonl" ]; then
  DONE=$(wc -l < "data/ko/questions_back.jsonl" | tr -d ' ')
  echo "  [Resume] 이미 ${DONE}건 완료, 이어서 실행"
fi

python3 scripts/translate/back_translate.py \
  --provider openai \
  --model gpt-4o-mini

echo "[OK] 역번역 완료: data/ko/questions_back.jsonl"

# ── Step 2: 번역 validity 채점 ────────────────────────────────────────────────
echo ""
echo "[Step 2/2] 번역 validity 3차원 채점..."
echo "  출력: data/ko/results/results_translation_validity.csv"
echo "  출력: data/ko/results/results_translation_validity_per_category.csv"

python3 scripts/analysis/analyze_translation_validity.py \
  --provider openai \
  --model gpt-4o-mini

echo ""
echo "=============================="
echo " 번역 품질 검증 완료"
echo " 결과 파일:"
ls -lh data/ko/results/results_translation_validity*.csv 2>/dev/null || echo "  (없음)"
echo " Date: $(date)"
echo "=============================="
