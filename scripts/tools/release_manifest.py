"""Shared allowlist for files covered by ``data/MANIFEST.sha256``."""

from __future__ import annotations

from pathlib import Path


JUDGMENT_PROTOCOLS = {
    "pairwise",
    "pairwise_ref",
    "single_grade",
    "single_grade_ref",
}


def is_published_data_file(path: Path, data_root: Path, manifest: Path) -> bool:
    """Return whether ``path`` is a canonical, published data artifact."""
    if not path.is_file() or path == manifest:
        return False

    parts = path.relative_to(data_root).parts
    if len(parts) == 1:
        return False
    if parts[0] == "results":
        return len(parts) == 2 and path.suffix == ".csv"
    if parts[0] == "translation_review":
        return len(parts) == 2 and path.suffix == ".csv"
    if parts[0] not in {"en", "ko"}:
        return False

    if len(parts) == 2:
        return parts[1] == "questions.jsonl"

    if parts[1] == "answers":
        return len(parts) == 3 and path.suffix == ".jsonl"

    if parts[1] == "judgments":
        return (
            len(parts) == 6
            and parts[4] in JUDGMENT_PROTOCOLS
            and path.suffix == ".jsonl"
        )

    return False
