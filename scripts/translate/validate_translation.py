#!/usr/bin/env python3
"""
scripts/translate/validate_translation.py

수작업으로 번역한 ``data/ko/questions.jsonl``의 구조와 핵심 제약을 검증한다.

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
        default=str(PROJECT_ROOT / "data" / "en" / "questions.jsonl"),
    )
    parser.add_argument(
        "--ko",
        default=str(PROJECT_ROOT / "data" / "ko" / "questions.jsonl"),
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

    orig_by_id: dict = {}
    with open(orig_path, encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line.strip())
            orig_by_id[obj["question_id"]] = obj

    errors = []
    warnings = []

    ko_by_id: dict = {}
    duplicate_ids = []
    with open(ko_path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                question_id = obj["question_id"]
                if question_id in ko_by_id:
                    duplicate_ids.append(question_id)
                ko_by_id[question_id] = obj
            except json.JSONDecodeError as e:
                errors.append(f"{lineno}번째 줄 JSON 파싱 실패: {e}")

    if duplicate_ids:
        errors.append(f"중복 question_id: {sorted(set(duplicate_ids))}")

    missing = sorted(set(orig_by_id) - set(ko_by_id))
    if missing:
        errors.append(f"번역 누락 문항 {len(missing)}개: {missing[:5]}{'...' if len(missing) > 5 else ''}")

    extra = sorted(set(ko_by_id) - set(orig_by_id))
    if extra:
        warnings.append(f"원본에 없는 question_id: {extra}")

    no_korean = []
    wrong_turn_count = []
    category_mismatch = []
    missing_reference = []

    for qid in sorted(set(orig_by_id) & set(ko_by_id)):
        orig = orig_by_id[qid]
        ko = ko_by_id[qid]

        if ko.get("category") != orig.get("category"):
            category_mismatch.append(
                (qid, orig.get("category"), ko.get("category"))
            )

        if len(ko["turns"]) != len(orig["turns"]):
            wrong_turn_count.append(qid)
            continue

        for t in ko["turns"]:
            if not has_korean(t):
                no_korean.append(qid)
                break

        if orig.get("reference") and not ko.get("reference"):
            missing_reference.append(qid)
        elif orig.get("reference") and ko.get("reference"):
            if len(ko["reference"]) != len(orig["reference"]):
                errors.append(f"q{qid} reference 개수 불일치")

    if wrong_turn_count:
        errors.append(f"turns 개수 불일치 {len(wrong_turn_count)}개: {wrong_turn_count[:5]}")
    if category_mismatch:
        errors.append(
            "qid별 category 불일치: "
            + ", ".join(
                f"q{qid}({original}→{translated})"
                for qid, original, translated in category_mismatch[:10]
            )
        )
    if no_korean:
        warnings.append(f"한글 미포함 문항 {len(no_korean)}개: {no_korean[:5]}")
    if missing_reference:
        warnings.append(
            f"reference 번역 누락 {len(missing_reference)}개: {missing_reference[:5]}"
        )

    q136 = ko_by_id.get(136)
    if q136:
        direction_text = q136["turns"][0]
        if "적은 순" in direction_text:
            expected_reference = [
                "you, 2\nriver, 6\nAmazon, 7",
                "to, 4\nand, 5\nthe, 17",
            ]
        elif "많은 순" in direction_text:
            expected_reference = [
                "Amazon, 7\nriver, 6\nyou, 2",
                "the, 17\nand, 5\nto, 4",
            ]
        else:
            expected_reference = None
            warnings.append("q136의 등장 횟수 정렬 방향이 명시되지 않음")
        if expected_reference is not None and q136.get("reference") != expected_reference:
            errors.append(
                "q136 reference가 지시문의 정렬 방향 또는 검증된 횟수와 불일치"
            )

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

    print("\n카테고리별 번역 현황:")
    cat_counts: dict = {}
    for ko in ko_by_id.values():
        cat = ko.get("category", "unknown")
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    for cat, cnt in sorted(cat_counts.items()):
        total = sum(1 for o in orig_by_id.values() if o["category"] == cat)
        status = "✓" if cnt == total else f"△ ({cnt}/{total})"
        print(f"  {cat:<14} {status}")

    if errors:
        sys.exit(1)

if __name__ == "__main__":
    main()
