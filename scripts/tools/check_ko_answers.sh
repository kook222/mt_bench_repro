#!/bin/bash
# scripts/tools/check_ko_answers.sh
#
# 한국어 답변 생성 결과 확인 스크립트.
# 각 모델의 답변 파일에서 샘플을 뽑아 한글/영어 여부를 빠르게 점검.
#
# 사용법:
#   bash scripts/tools/check_ko_answers.sh
#   bash scripts/tools/check_ko_answers.sh --n 5   # 모델당 5개 샘플

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
ANSWERS_DIR="$PROJECT_DIR/data/ko/answers"
N="${2:-3}"   # 모델당 출력 샘플 수 (기본 3)

EVAL_MODELS=(
  "Llama-3.1-8B-Instruct"
  "SOLAR-10.7B-Instruct"
  "gemma-2-9b-it"
  "Mistral-7B-Instruct-v0.3"
  "Phi-3.5-mini-Instruct"
)

echo "============================================================"
echo " 한국어 답변 샘플 확인 (모델당 ${N}개)"
echo " 경로: $ANSWERS_DIR"
echo "============================================================"

for MODEL_ID in "${EVAL_MODELS[@]}"; do
  FPATH="$ANSWERS_DIR/${MODEL_ID}.jsonl"

  echo ""
  echo "────────────────────────────────────────────"
  echo " 모델: $MODEL_ID"
  echo "────────────────────────────────────────────"

  if [ ! -f "$FPATH" ]; then
    echo "  [MISS] 파일 없음 — 아직 생성 안 됨"
    continue
  fi

  TOTAL=$(wc -l < "$FPATH" | tr -d ' ')
  echo "  총 ${TOTAL}줄 (80문항 × 2턴 = 160줄 완료 기대)"

  echo ""
  echo "  --- 샘플 답변 (Turn 1, question_id 순) ---"
  # turn_id=1인 항목만 첫 N개 출력
  python3 - <<PYEOF
import json, sys

path = "$FPATH"
n = $N
count = 0
with open(path) as f:
    for line in f:
        obj = json.loads(line)
        if obj.get("turn_id", obj.get("turn", 0)) != 1:
            continue
        qid = obj.get("question_id", "?")
        choices = obj.get("choices", [{}])
        text = choices[0].get("turns", [""])[0] if choices else ""
        preview = text[:200].replace("\n", " ")
        print(f"  Q{qid}: {preview}...")
        count += 1
        if count >= n:
            break

# 한글 포함 비율 체크
total_chars = 0
korean_chars = 0
with open(path) as f:
    for line in f:
        obj = json.loads(line)
        choices = obj.get("choices", [{}])
        for turn_text in choices[0].get("turns", []):
            for ch in turn_text:
                total_chars += 1
                if '가' <= ch <= '힣':
                    korean_chars += 1

ratio = korean_chars / total_chars * 100 if total_chars > 0 else 0
flag = "✅" if ratio > 10 else "⚠️  한글 비율 낮음!"
print(f"\n  한글 문자 비율: {ratio:.1f}% {flag}")
PYEOF

done

echo ""
echo "============================================================"
echo " 완료. 한글 비율 10% 미만이면 모델이 영어로 답변한 것."
echo "============================================================"
