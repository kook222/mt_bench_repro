#!/usr/bin/env python3
"""Validate the publishable Korean MT-Bench artifact without network access."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.analysis import build_paper_artifacts as paper  # noqa: E402
from scripts.tools.release_manifest import is_published_data_file  # noqa: E402


EXPECTED_CATEGORIES = set(paper.CATEGORY_ORDER)
EXPECTED_MODELS = set(paper.MODEL_ORDER)
FASTCHAT_QUESTIONS_SHA256 = (
    "119565adbab82227089cefdb44c8d7e2cf04dc0a0ec233634c82e7d4e2a944f7"
)
Q136_REFERENCE = [
    "you, 2\nriver, 6\nAmazon, 7",
    "to, 4\nand, 5\nthe, 17",
]
RESULT_FILES = {
    "table4_translation_review.csv",
    "table5_pairwise_inconsistency.csv",
    "table6_single_scores.csv",
    "table7_reference_scores.csv",
    "table8_parse_failures.csv",
    "figure3_scores.csv",
}
SECRET_PATTERNS = {
    "OpenAI-style key": re.compile(r"\b(?:sk|rk|pk)-[A-Za-z0-9_-]{32,}\b"),
    "GitHub token": re.compile(
        r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"
    ),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "Hugging Face token": re.compile(r"\bhf_[A-Za-z0-9]{30,}\b"),
}
TEXT_SUFFIXES = {
    ".cfg",
    ".csv",
    ".ini",
    ".jinja",
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
FALLBACK_IGNORED_DIRS = {
    ".git",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".vscode",
    "__pycache__",
    "generated",
    "models",
    "runs",
    "venv",
}
FALLBACK_IGNORED_SUFFIXES = {
    ".bak",
    ".bin",
    ".ckpt",
    ".log",
    ".out",
    ".pt",
    ".pth",
    ".pyc",
    ".pyo",
    ".safetensors",
    ".swp",
}
FALLBACK_IGNORED_FILENAMES = {".coverage", ".DS_Store", "secrets.yaml"}


class Validation:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def check(self, condition: bool, message: str) -> None:
        print(f"[{'OK' if condition else 'FAIL'}] {message}")
        if not condition:
            self.failures.append(message)


def reject_nonstandard_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON numeric constant: {value}")


def path_is_relative_to(path: Path, root: Path) -> bool:
    """Return whether path is below root, including on Python 3.8."""
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            value = json.loads(line, parse_constant=reject_nonstandard_json_constant)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: expected a JSON object")
            rows.append(value)
    return rows


def fallback_public_files(root: Path) -> tuple[Path, ...]:
    """List release files when ``.git`` is absent, as in GitHub ZIP archives.

    The exclusions mirror the repository's local-only ``.gitignore`` entries.
    Manuscripts and arbitrary extra Markdown files are intentionally *not*
    excluded so the normal public-tree checks can still reject them.
    """
    paths: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(
            part in FALLBACK_IGNORED_DIRS or part.endswith(".egg-info")
            for part in relative.parts[:-1]
        ):
            continue
        if path.name in FALLBACK_IGNORED_FILENAMES:
            continue
        if path.name == ".env" or path.name.startswith(".env."):
            continue
        if path.suffix.lower() in FALLBACK_IGNORED_SUFFIXES:
            continue
        if relative.as_posix() == "data/ko/questions_back.jsonl":
            continue
        paths.append(path)
    return tuple(sorted(paths))


def public_files() -> tuple[Path, ...]:
    if not (ROOT / ".git").exists():
        return fallback_public_files(ROOT)
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return fallback_public_files(ROOT)
    return tuple(
        path
        for raw in result.stdout.decode("utf-8").split("\0")
        if raw and (path := ROOT / raw).is_file()
    )


def all_text_files() -> Iterable[Path]:
    for path in public_files():
        if path.suffix.lower() in TEXT_SUFFIXES or path.name == "Makefile":
            yield path


def validate_questions(validation: Validation) -> tuple[set[int], set[int]]:
    en_path = ROOT / "data" / "en" / "questions.jsonl"
    ko_path = ROOT / "data" / "ko" / "questions.jsonl"
    validation.check(en_path.is_file() and ko_path.is_file(), "EN and KO question files are present")
    validation.check(
        hashlib.sha256(en_path.read_bytes()).hexdigest() == FASTCHAT_QUESTIONS_SHA256,
        "English questions match the pinned FastChat source",
    )

    en_rows = read_jsonl(en_path)
    ko_rows = read_jsonl(ko_path)
    en_ids = {int(row["question_id"]) for row in en_rows}
    ko_ids = {int(row["question_id"]) for row in ko_rows}
    ko_categories = Counter(str(row.get("category")) for row in ko_rows)
    validation.check(len(en_rows) == len(ko_rows) == 80, "EN and KO contain 80 questions")
    validation.check(len(en_ids) == len(ko_ids) == 80 and en_ids == ko_ids, "question IDs are unique and aligned")
    validation.check(
        all(
            isinstance(row.get("turns"), list)
            and len(row["turns"]) == 2
            and all(isinstance(turn, str) and turn.strip() for turn in row["turns"])
            for row in (*en_rows, *ko_rows)
        ),
        "every question contains two non-empty turns",
    )
    validation.check(
        set(ko_categories) == EXPECTED_CATEGORIES
        and all(value == 10 for value in ko_categories.values()),
        "Korean questions contain ten items in each of eight categories",
    )
    validation.check(
        {int(row["question_id"]): row["category"] for row in en_rows}
        == {int(row["question_id"]): row["category"] for row in ko_rows},
        "EN and KO categories match by question ID",
    )

    by_id = {int(row["question_id"]): row for row in ko_rows}
    validation.check(
        "200단어 미만" in by_id[83]["turns"][0]
        and "200글자" not in by_id[83]["turns"][0],
        "q83 preserves the word-count unit",
    )
    validation.check(
        all(
            marker in by_id[90]["turns"][0]
            for marker in ("지갑를", "지갑이 찾아봐", "대답됬다", "찾았냬")
        ),
        "q90 contains the intended Korean correction task",
    )
    validation.check(
        "The Amazon" in by_id[136]["turns"][0]
        and "적은 순서" in by_id[136]["turns"][0]
        and by_id[136].get("reference") == Q136_REFERENCE,
        "q136 preserves the counting passage and output order",
    )
    reference_ids = {
        int(row["question_id"])
        for row in en_rows
        if row.get("reference") is not None
        and row.get("category") in {"reasoning", "math", "coding"}
    }
    validation.check(len(reference_ids) == 29, "reference protocol contains 29 declared questions")
    return en_ids, reference_ids


def validate_answers(validation: Validation, expected_ids: set[int]) -> None:
    for language in paper.LANGUAGES:
        paths = sorted((ROOT / "data" / language / "answers").glob("*.jsonl"))
        validation.check(
            {path.stem for path in paths} == EXPECTED_MODELS,
            f"{language.upper()} answers contain the six generation models",
        )
        valid = True
        for path in paths:
            rows = read_jsonl(path)
            valid = valid and len(rows) == 80
            valid = valid and {row.get("question_id") for row in rows} == expected_ids
            valid = valid and all(
                row.get("model_id") == path.stem
                and isinstance(row.get("choices"), list)
                and row["choices"]
                and isinstance(row["choices"][0].get("turns"), list)
                and len(row["choices"][0]["turns"]) == 2
                for row in rows
            )
        validation.check(valid, f"each {language.upper()} answer file has 80 complete records")


def validate_judgments(
    validation: Validation,
    expected_ids: set[int],
    reference_ids: set[int],
) -> tuple[paper.JudgeSpec, ...]:
    data_root = ROOT / "data"
    gemma = next(judge for judge in paper.JUDGES if judge.optional)
    gemma_files = tuple(
        path
        for language in paper.LANGUAGES
        for path in (data_root / language / "judgments" / gemma.relative_dir).rglob("*.jsonl")
    )
    if gemma_files:
        validation.check(
            paper.complete_judge_matrix(data_root, gemma),
            "Gemma 4 judgment matrix is complete in both languages",
        )
    judges = paper.active_judges(data_root)
    validation.check(
        len(judges) == 6,
        "six judges are recognized",
    )

    expected_pairs = {
        tuple(sorted((model_a, model_b)))
        for model_a in EXPECTED_MODELS
        for model_b in EXPECTED_MODELS
        if model_a < model_b
    }
    for language in paper.LANGUAGES:
        categories = {
            int(row["question_id"]): row["category"]
            for row in read_jsonl(data_root / language / "questions.jsonl")
        }
        language_total = 0
        for judge in judges:
            root = data_root / language / "judgments" / judge.relative_dir
            matrix_valid = True
            for protocol, protocol_ids in (
                ("single_grade", expected_ids),
                ("single_grade_ref", reference_ids),
            ):
                paths = sorted((root / protocol).glob("*.jsonl"))
                matrix_valid = matrix_valid and {path.stem for path in paths} == EXPECTED_MODELS
                for path in paths:
                    rows = read_jsonl(path)
                    language_total += len(rows)
                    matrix_valid = matrix_valid and len(rows) == len(protocol_ids)
                    matrix_valid = matrix_valid and {row.get("question_id") for row in rows} == protocol_ids
                    matrix_valid = matrix_valid and all(
                        row.get("model_id") == path.stem
                        and row.get("judge_id") == judge.judge_id
                        and row.get("category") == categories[int(row["question_id"])]
                        for row in rows
                    )

            pair_paths = sorted((root / "pairwise").glob("*.jsonl"))
            observed_pairs: set[tuple[str, str]] = set()
            matrix_valid = matrix_valid and len(pair_paths) == 15
            for path in pair_paths:
                rows = read_jsonl(path)
                language_total += len(rows)
                file_pairs = {
                    tuple(sorted((str(row.get("model_a")), str(row.get("model_b")))))
                    for row in rows
                }
                observed_pairs.update(file_pairs)
                matrix_valid = matrix_valid and len(rows) == 80 and len(file_pairs) == 1
                matrix_valid = matrix_valid and {row.get("question_id") for row in rows} == expected_ids
                matrix_valid = matrix_valid and all(
                    row.get("judge_id") == judge.judge_id
                    and row.get("category") == categories[int(row["question_id"])]
                    for row in rows
                )
            matrix_valid = matrix_valid and observed_pairs == expected_pairs
            validation.check(
                matrix_valid,
                f"{language.upper()} {judge.display} has the complete 6/15/6 judgment matrix",
            )
        validation.check(
            language_total == 1_854 * len(judges),
            f"{language.upper()} judgment record count matches {len(judges)} judges",
        )
    return judges


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def validate_results(validation: Validation, judges: tuple[paper.JudgeSpec, ...]) -> None:
    results_dir = ROOT / "data" / "results"
    paths = {path.name for path in results_dir.glob("*.csv")}
    validation.check(paths == RESULT_FILES, "only paper-aligned result CSVs are published")

    table4 = read_csv(results_dir / "table4_translation_review.csv")
    validation.check(
        len(table4) == 8
        and sum(int(row["manual_review_candidates"]) for row in table4) == 34
        and sum(int(row["modified_items"]) for row in table4) == 3,
        "translation table records 34 candidates and three finalized changes",
    )
    table5 = read_csv(results_dir / "table5_pairwise_inconsistency.csv")
    validation.check(
        len(table5) == len(judges) + 1
        and table5[-1]["judge"] == "Mean"
        and {row["judge"] for row in table5[:-1]}
        == {judge.display for judge in judges}
        and table5[0]["en_rate_pct"] == "79.25"
        and table5[0]["ko_rate_pct"] == "45.07"
        and table5[-2]["judge"] == "Gemma-4-12B"
        and table5[-2]["en_inconsistent"] == "234"
        and table5[-2]["en_valid"] == "1180"
        and table5[-2]["en_rate_pct"] == "19.83"
        and table5[-2]["ko_inconsistent"] == "176"
        and table5[-2]["ko_valid"] == "1197"
        and table5[-2]["ko_rate_pct"] == "14.7"
        and table5[-2]["delta_ko_minus_en_pp"] == "-5.13"
        and table5[-2]["ko_same_first"] == "108"
        and table5[-2]["ko_same_first_pct"] == "61.36"
        and table5[-2]["ko_same_second"] == "54"
        and table5[-2]["ko_same_second_pct"] == "30.68"
        and table5[-1]["en_rate_pct"] == "41.79"
        and table5[-1]["ko_rate_pct"] == "25.92"
        and table5[-1]["delta_ko_minus_en_pp"] == "-15.87"
        and all(
            int(row["ko_same_first"])
            + int(row["ko_same_second"])
            + int(row["ko_other_inconsistent"])
            == int(row["ko_inconsistent"])
            for row in table5[:-1]
        ),
        "pairwise table reports all six judges and the six-judge mean",
    )
    table6 = read_csv(results_dir / "table6_single_scores.csv")
    validation.check(
        len(table6) == len(judges) + 1
        and {row["judge"] for row in table6[:-1]}
        == {judge.display for judge in judges}
        and table6[-2]["judge"] == "Gemma-4-12B"
        and table6[-2]["en_mean"] == "7.51"
        and table6[-2]["en_valid_scores"] == "957"
        and table6[-2]["ko_mean"] == "5.56"
        and table6[-2]["ko_valid_scores"] == "956"
        and table6[-2]["delta_ko_minus_en"] == "-1.95"
        and table6[-1]["en_mean"] == "7.78"
        and table6[-1]["ko_mean"] == "6.47"
        and table6[-1]["delta_ko_minus_en"] == "-1.3"
        and all(
            int(row["en_valid_scores"]) <= 960
            and int(row["ko_valid_scores"]) <= 960
            for row in table6[:-1]
        ),
        "single-score table reports all six judges and valid denominators",
    )
    table7 = read_csv(results_dir / "table7_reference_scores.csv")
    validation.check(
        len(table7) == len(judges) + 1
        and {row["judge"] for row in table7[:-1]}
        == {judge.display for judge in judges}
        and table7[-2]["judge"] == "Gemma-4-12B"
        and table7[-2]["en_standard_mean"] == "5.23"
        and table7[-2]["en_reference_mean"] == "4.65"
        and table7[-2]["en_delta"] == "-0.59"
        and table7[-2]["en_paired"] == "172"
        and table7[-2]["ko_standard_mean"] == "4.45"
        and table7[-2]["ko_reference_mean"] == "3.95"
        and table7[-2]["ko_delta"] == "-0.5"
        and table7[-2]["ko_paired"] == "173"
        and table7[-1]["en_standard_mean"] == "7.21"
        and table7[-1]["en_reference_mean"] == "5.76"
        and table7[-1]["en_delta"] == "-1.45"
        and table7[-1]["ko_standard_mean"] == "6.3"
        and table7[-1]["ko_reference_mean"] == "5.1"
        and table7[-1]["ko_delta"] == "-1.19"
        and all(int(row["en_paired"]) <= 174 and int(row["ko_paired"]) <= 174 for row in table7[:-1]),
        "reference table reports all six judges and paired valid outputs",
    )
    table8 = read_csv(results_dir / "table8_parse_failures.csv")
    table8_keyed = {
        (row["language"], row["judge"], row["protocol"]): row
        for row in table8
    }
    gemma_failures = {
        ("en", "single_grade"): (960, 957, 3),
        ("en", "pairwise"): (2400, 2380, 20),
        ("en", "single_grade_ref"): (174, 174, 0),
        ("ko", "single_grade"): (960, 956, 4),
        ("ko", "pairwise"): (2400, 2397, 3),
        ("ko", "single_grade_ref"): (174, 174, 0),
    }
    validation.check(
        len(table8) == len(judges) * 2 * 3
        and {row["judge"] for row in table8}
        == {judge.display for judge in judges}
        and all(
            int(row["valid_calls"])
            + int(row["format_parse_failures"])
            + int(row["empty_or_api_failures"])
            + int(row["missing_calls"])
            == int(row["expected_calls"])
            for row in table8
        )
        and all(
            (
                int(table8_keyed[(language, "Gemma-4-12B", protocol)]["expected_calls"]),
                int(table8_keyed[(language, "Gemma-4-12B", protocol)]["valid_calls"]),
                int(table8_keyed[(language, "Gemma-4-12B", protocol)]["format_parse_failures"]),
            )
            == expected
            and table8_keyed[(language, "Gemma-4-12B", protocol)]["empty_or_api_failures"] == "0"
            and table8_keyed[(language, "Gemma-4-12B", protocol)]["missing_calls"] == "0"
            for (language, protocol), expected in gemma_failures.items()
        ),
        "failure table accounts for every evaluation call from all six judges",
    )

    figure_rows = read_csv(results_dir / "figure3_scores.csv")
    validation.check(
        len(figure_rows) == 28
        and set(figure_rows[0])
        == {
            "language",
            "row_type",
            "row_order",
            "row_id",
            "row_label",
            *(judge.key for judge in judges),
            "judge_mean",
        },
        "Figure data contains all six judges across both languages",
    )

def validate_public_tree(validation: Validation) -> None:
    files = public_files()
    markdown = {path.relative_to(ROOT).as_posix() for path in files if path.suffix.lower() == ".md"}
    validation.check(markdown == {"README.md"}, "README is the only published Markdown document")
    manuscript_suffixes = {".doc", ".docx", ".hwp", ".hwpx", ".tex"}
    validation.check(
        not any(path.suffix.lower() in manuscript_suffixes for path in files),
        "no manuscript or submission file is present",
    )
    validation.check((ROOT / "LICENSE").is_file(), "Apache 2.0 license is present")
    validation.check(
        not any(path.suffix.lower() in {".png", ".pdf", ".svg"} for path in files),
        "generated figure binaries are excluded from the public repository",
    )


def validate_manifest(validation: Validation) -> None:
    manifest = ROOT / "data" / "MANIFEST.sha256"
    data_root = ROOT / "data"
    data_files = {path for path in public_files() if path_is_relative_to(path, data_root)}
    unexpected = {
        path.relative_to(ROOT).as_posix()
        for path in data_files
        if path != manifest and not is_published_data_file(path, data_root, manifest)
    }
    validation.check(not unexpected, "all published data files match the allowlist")
    for path in sorted(unexpected):
        print(f"      unexpected data file: {path}")

    expected = {
        path.relative_to(ROOT).as_posix()
        for path in data_files
        if is_published_data_file(path, data_root, manifest)
    }
    recorded: set[str] = set()
    valid = manifest.is_file()
    if manifest.is_file():
        for line in manifest.read_text(encoding="utf-8").splitlines():
            digest, separator, relative = line.partition("  ")
            path = ROOT / relative
            recorded.add(relative)
            valid = valid and bool(separator) and path.is_file()
            if path.is_file():
                valid = valid and hashlib.sha256(path.read_bytes()).hexdigest() == digest
    validation.check(valid and recorded == expected, "data manifest covers every published data file")


def validate_secrets(validation: Validation) -> None:
    findings: list[str] = []
    for path in all_text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{path.relative_to(ROOT)} ({label})")
    for finding in findings:
        print(f"      possible secret: {finding}")
    validation.check(not findings, "no representative API key pattern is present")


def main() -> int:
    validation = Validation()
    try:
        question_ids, reference_ids = validate_questions(validation)
        validate_answers(validation, question_ids)
        judges = validate_judgments(validation, question_ids, reference_ids)
        validate_results(validation, judges)
        validate_public_tree(validation)
        validate_manifest(validation)
        validate_secrets(validation)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, KeyError, StopIteration) as error:
        validation.failures.append(str(error))
        print(f"[FAIL] validation aborted: {error}")

    if validation.failures:
        print(f"\nRelease validation failed: {len(validation.failures)} problem(s).")
        return 1
    print("\nRelease validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
