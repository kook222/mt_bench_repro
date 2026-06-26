#!/usr/bin/env python3
"""
scripts/tools/clean_truncation_errors.py

pairwise JSONL 파일에서 truncation 에러 건 제거.
- 대상: winner_ab == 'error' 또는 winner_ba == 'error'이면서 judgment가 빈 문자열인 건
- resume 로직이 question_id 기준 skip이므로, 재실행 전 반드시 이 스크립트로 정리 필요.

Usage:
    cd mt_bench_repro
    python3 scripts/tools/clean_truncation_errors.py          # en + ko 모두
    python3 scripts/tools/clean_truncation_errors.py --lang en
    python3 scripts/tools/clean_truncation_errors.py --lang ko
"""

import argparse
import json
import shutil
from pathlib import Path


def is_truncation_error(entry: dict) -> bool:
    """judgment가 비어있는 에러 건 = truncation."""
    ab_err = entry.get("winner_ab") == "error" and entry.get("judgment_ab", "") == ""
    ba_err = entry.get("winner_ba") == "error" and entry.get("judgment_ba", "") == ""
    return ab_err or ba_err


def clean_file(path: Path, dry_run: bool = False):
    """
    파일에서 truncation 에러 건 제거.
    Returns: (total, removed)
    """
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    kept = []
    removed = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            kept.append(line)
            continue

        if is_truncation_error(entry):
            removed += 1
        else:
            kept.append(line)

    total = len(kept) + removed

    if removed > 0 and not dry_run:
        # 백업
        backup = path.with_suffix(".jsonl.bak")
        shutil.copy2(path, backup)
        # 덮어쓰기
        path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")

    return total, removed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", choices=["en", "ko", "both"], default="both")
    parser.add_argument("--dry-run", action="store_true", help="실제 수정 없이 대상 건수만 출력")
    parser.add_argument("--judge", default="judge_32B", help="judge 폴더명 (default: judge_32B)")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]  # mt_bench_repro/

    langs = ["en", "ko"] if args.lang == "both" else [args.lang]

    total_removed = 0
    for lang in langs:
        pairwise_dir = root / "data" / lang / "judgments" / "qwen" / args.judge / "pairwise"
        if not pairwise_dir.exists():
            print(f"[SKIP] 디렉토리 없음: {pairwise_dir}")
            continue

        jsonl_files = sorted(pairwise_dir.glob("*.jsonl"))
        if not jsonl_files:
            print(f"[SKIP] JSONL 파일 없음: {pairwise_dir}")
            continue

        print(f"\n[{lang.upper()}] {pairwise_dir}")
        for f in jsonl_files:
            total, removed = clean_file(f, dry_run=args.dry_run)
            if removed > 0:
                tag = "[DRY-RUN] " if args.dry_run else ""
                print(f"  {tag}{f.name}: {total}건 중 {removed}건 truncation 제거")
                total_removed += removed
            else:
                print(f"  {f.name}: OK (에러 없음)")

    print(f"\n총 {total_removed}건 {'제거 예정' if args.dry_run else '제거 완료'}.")
    if total_removed > 0 and not args.dry_run:
        print("백업: 각 파일과 동일 위치에 .jsonl.bak 생성됨.")


if __name__ == "__main__":
    main()
