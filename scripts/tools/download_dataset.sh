#!/bin/bash
# scripts/tools/download_dataset.sh
# FastChat 공식 저장소에서 MT-Bench 80문항 데이터셋을 다운로드한다.
#
# 논문: NeurIPS 2023 "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena"
# 원본 데이터: https://github.com/lm-sys/FastChat/tree/main/fastchat/llm_judge/data/mt_bench
#
# 카테고리별 10문항 × 8개 = 80문항:
#   writing, roleplay, extraction, reasoning,
#   math, coding, stem, humanities

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

DEST="data/mt_bench_questions.jsonl"
FASTCHAT_URL="https://raw.githubusercontent.com/lm-sys/FastChat/main/fastchat/llm_judge/data/mt_bench/question.jsonl"

echo "=============================="
echo " MT-Bench 데이터셋 다운로드"
echo "=============================="

echo ""
echo "다운로드 중: $FASTCHAT_URL"
curl -L --retry 3 --retry-delay 2 \
    "$FASTCHAT_URL" \
    -o "$DEST"

echo ""
echo "다운로드 완료: $DEST"
echo "총 문항 수: $(wc -l < "$DEST")"

echo ""
echo "카테고리별 문항 수:"
python3 -c "
import json
from collections import Counter
cats = Counter()
for line in open('$DEST'):
    line = line.strip()
    if not line:
        continue
    q = json.loads(line)
    cats[q['category']] += 1
for cat, cnt in sorted(cats.items()):
    print(f'  {cat:<15} {cnt}개')
print(f'  {\"합계\":<15} {sum(cats.values())}개')
"

echo ""
echo "reference 있는 문항 수:"
python3 -c "
import json
with_ref = sum(
    1 for line in open('$DEST')
    if line.strip() and json.loads(line).get('reference')
)
print(f'  reference 있음: {with_ref}개 (math/coding/reasoning 주로)')
"
