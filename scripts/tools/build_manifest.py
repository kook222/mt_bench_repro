#!/usr/bin/env python3
"""Build deterministic SHA-256 checksums for every published data file."""

from __future__ import annotations

import hashlib
from pathlib import Path

from release_manifest import is_published_data_file


ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = ROOT / "data"
OUTPUT = DATA_ROOT / "MANIFEST.sha256"

def main() -> None:
    paths = sorted(
        path
        for path in DATA_ROOT.rglob("*")
        if is_published_data_file(path, DATA_ROOT, OUTPUT)
    )
    lines = []
    for path in paths:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(ROOT).as_posix()}\n")
    OUTPUT.write_text("".join(lines), encoding="utf-8")
    print(f"[OK] wrote {OUTPUT} ({len(paths)} files)")


if __name__ == "__main__":
    main()
