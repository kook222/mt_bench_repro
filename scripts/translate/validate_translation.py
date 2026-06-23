#!/usr/bin/env python3
"""
scripts/translate/validate_translation.py

수작업으로 번역한 mt_bench_questions_ko.jsonl 파일의 형식을 검증한다.

수작업 번역 저장 형식:
  원본과 동일한 JSONL 구조, turns[]와 reference[]만 한국어로 교체.

  {"question_id": 81, "category": "writing",
   "turns": ["한국어 Turn1", "한국어 Turn2"]}

  {"question_id": 101, "category": "math",
   "turns": ["한국어 Turn1", "한국어 Turn2"],
   "reference": ["한국어 참조답변1", "한국어 참조답변2"]}

사용법:
    export PYTHONPATH=src
    python3 scripts/translate/validate_translation.py
    python3 scripts/translate/validate_translation.py --ko data/ko/questions.jsonl
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def has_korean(text: str) -> bool:
    return any("가" <= ch <= "힣" for ch in text)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--original",
        default=str(PROJECT_ROOT / "data" / "mt_bench_questions.jsonl"),
    )
    parser.add_argument(
        "--ko",
        default=str(PROJECT_ROOT / "data" / "mt_bench_questions_ko.jsonl"),
    )
    args = parser.parse_args()

    orig_path = Path(args.original)
    ko_path = Path(args.ko)

    if not ko_path.exists():
        print(f"[오류] 번역 파일 없음: {ko_path}")
        print()
        print("저장 형식 예시:")
        with open(orig_path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= 2:
                    break
                obj = json.loads(line.strip())
                print(f"  {json.dumps(obj, ensure_ascii=False)}")
        sys.exit(1)

    # 원본 로드
    orig_by_id: dict = {}
    with open(orig_path, encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line.strip())
            orig_by_id[obj["question_id"]] = obj

    # 번역본 로드 및 검증
    ko_by_id: dict = {}
    with open(ko_path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                ko_by_id[obj["question_id"]] = obj
            except json.JSONDecodeError as e:
                print(f"[오류] {lineno}번째 줄 JSON 파싱 실패: {e}")

    errors = []
    warnings = []

    # 커버리지 확인
    missing = sorted(set(orig_by_id) - set(ko_by_id))
    if missing:
        errors.append(f"번역 누락 문항 {len(missing)}개: {missing[:5]}{'...' if len(missing) > 5 else ''}")

    extra = sorted(set(ko_by_id) - set(orig_by_id))
    if extra:
        warnings.append(f"원본에 없는 question_id: {extra}")

    # 각 문항 검증
    no_korean = []
    wrong_turn_count = []
    missing_reference = []

    for qid in sorted(set(orig_by_id) & set(ko_by_id)):
        orig = orig_by_id[qid]
        ko = ko_by_id[qid]

        # turns 개수 확인
        if len(ko["turns"]) != len(orig["turns"]):
            wrong_turn_count.append(qid)
            continue

        # 한글 포함 여부
        for t in ko["turns"]:
            if not has_korean(t):
                no_korean.append(qid)
                break

        # reference 있어야 할 문항 확인
        if orig.get("reference") and not ko.get("reference"):
            missing_reference.append(qid)
        elif orig.get("reference") and ko.get("reference"):
            if len(ko["reference"]) != len(orig["reference"]):
                errors.append(f"q{qid} reference 개수 불일치")

    if wrong_turn_count:
        errors.append(f"turns 개수 불일치 {len(wrong_turn_count)}개: {wrong_turn_count[:5]}")
    if no_korean:
        warnings.append(f"한글 미포함 문항 {len(no_korean)}개: {no_korean[:5]}")
    if missing_reference:
        warnings.append(
            f"reference 번역 누락 {len(missing_reference)}개: {missing_reference[:5]}"
        )

    # 결과 출력
    print(f"[검증] 원본 {len(orig_by_id)}개 / 번역본 {len(ko_by_id)}개")
    if errors:
        print("\n[오류]")
        for e in errors:
            print(f"  ✗ {e}")
    if warnings:
        print("\n[경고]")
        for w in warnings:
            print(f"  △ {w}")
    if not errors and not warnings:
        print("  ✓ 모든 검증 통과")
    elif not errors:
        print("\n  오류 없음 — 경고 항목만 확인하세요.")

    print(f"\n카테고리별 번역 현황:")
    cat_counts: dict = {}
    for ko in ko_by_id.values():
        cat = ko.get("category", "unknown")
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    for cat, cnt in sorted(cat_counts.items()):
        total = sum(1 for o in orig_by_id.values() if o["category"] == cat)
        status = "✓" if cnt == total else f"△ ({cnt}/{total})"
        print(f"  {cat:<14} {status}")


if __name__ == "__main__":
    main()
