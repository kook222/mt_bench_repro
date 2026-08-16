#!/usr/bin/env python3
"""Build the paper tables and four-panel Figure 3 from raw judgments."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Iterable, Sequence


ROOT = Path(__file__).resolve().parents[2]
LANGUAGES = ("en", "ko")
PROTOCOLS = ("single_grade", "pairwise", "single_grade_ref")
MODEL_ORDER = (
    "Llama-3.1-8B-Instruct",
    "EEVE-Korean-Instruct-10.8B",
    "EXAONE-3.5-7.8B-Instruct",
    "gemma-2-9b-it",
    "Mistral-7B-Instruct-v0.3",
    "Phi-3.5-mini-Instruct",
)
MODEL_DISPLAY = {
    "Llama-3.1-8B-Instruct": "Llama 3.1 8B",
    "EEVE-Korean-Instruct-10.8B": "EEVE 10.8B",
    "EXAONE-3.5-7.8B-Instruct": "EXAONE 7.8B",
    "gemma-2-9b-it": "Gemma 2 9B",
    "Mistral-7B-Instruct-v0.3": "Mistral 7B",
    "Phi-3.5-mini-Instruct": "Phi 3.5 Mini",
}
CATEGORY_ORDER = (
    "writing",
    "roleplay",
    "extraction",
    "reasoning",
    "math",
    "coding",
    "stem",
    "humanities",
)


@dataclass(frozen=True)
class JudgeSpec:
    key: str
    relative_dir: str
    judge_id: str
    display: str
    figure_display: str
    optional: bool = False


JUDGES = (
    JudgeSpec(
        "qwen_7b",
        "qwen/judge_7B",
        "Qwen2.5-7B-Instruct",
        "Qwen-7B",
        "Qwen\n7B",
    ),
    JudgeSpec(
        "qwen_14b",
        "qwen/judge_14B",
        "Qwen2.5-14B-Instruct",
        "Qwen-14B",
        "Qwen\n14B",
    ),
    JudgeSpec(
        "qwen_32b",
        "qwen/judge_32B",
        "Qwen2.5-32B-Instruct",
        "Qwen-32B",
        "Qwen\n32B",
    ),
    JudgeSpec(
        "exaone_32b",
        "exaone/judge_32B",
        "EXAONE-3.5-32B-Instruct-AWQ",
        "EXAONE-32B",
        "EXAONE\n32B",
    ),
    JudgeSpec(
        "gpt_4o_mini",
        "gpt/judge_gpt4omini",
        "gpt-4o-mini",
        "GPT-4o-mini",
        "GPT-4o\nmini",
    ),
    JudgeSpec(
        "gemma_4_12b",
        "gemma4/judge_12B",
        "Gemma-4-12B-it",
        "Gemma-4-12B",
        "Gemma-4\n12B",
        optional=True,
    ),
)

FIGURE_WIDTH_INCHES = 5.71
FIGURE_HEIGHT_INCHES = 3.70


def read_jsonl(path: Path) -> Iterable[dict]:
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: expected a JSON object")
            yield value


def latest_records(directory: Path, protocol: str) -> dict[tuple, dict]:
    records: dict[tuple, dict] = {}
    for path in sorted(directory.glob("*.jsonl")):
        for record in read_jsonl(path):
            if protocol == "pairwise":
                key = (
                    str(record.get("judge_id", "")),
                    *sorted((str(record.get("model_a", "")), str(record.get("model_b", "")))),
                    int(record["question_id"]),
                    int(record.get("turn", 2)),
                )
            else:
                key = (
                    str(record.get("judge_id", "")),
                    str(record.get("model_id", "")),
                    int(record["question_id"]),
                )
            current = records.get(key)
            if current is None or float(record.get("tstamp") or 0) >= float(
                current.get("tstamp") or 0
            ):
                records[key] = record
    return records


def complete_judge_matrix(data_root: Path, judge: JudgeSpec) -> bool:
    expected_file_counts = {"single_grade": 6, "pairwise": 15, "single_grade_ref": 6}
    for language in LANGUAGES:
        judge_root = data_root / language / "judgments" / judge.relative_dir
        for protocol, expected in expected_file_counts.items():
            paths = tuple((judge_root / protocol).glob("*.jsonl"))
            if len(paths) != expected:
                return False
    return True


def active_judges(data_root: Path) -> tuple[JudgeSpec, ...]:
    active: list[JudgeSpec] = []
    for judge in JUDGES:
        complete = complete_judge_matrix(data_root, judge)
        if not judge.optional and not complete:
            raise ValueError(f"incomplete required judgment matrix: {judge.display}")
        if complete:
            active.append(judge)
    return tuple(active)


def judge_root(data_root: Path, language: str, judge: JudgeSpec) -> Path:
    return data_root / language / "judgments" / judge.relative_dir


def valid_score(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def write_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build_translation_review(data_root: Path) -> list[dict]:
    source = data_root / "translation_review" / "items.csv"
    if not source.is_file():
        raise ValueError(f"missing translation review source: {source}")
    by_category: dict[str, list[dict[str, str]]] = defaultdict(list)
    with source.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            by_category[row["category"]].append(row)

    if set(by_category) != set(CATEGORY_ORDER):
        raise ValueError("translation review categories do not match MT-Bench")

    rows: list[dict] = []
    for category in CATEGORY_ORDER:
        items = by_category[category]
        rows.append(
            {
                "category": category,
                "n": len(items),
                "bleu_mean": round(mean(float(row["bleu_avg"]) for row in items), 4),
                "semantic_mean": round(
                    mean(float(row["semantic_avg"]) for row in items), 2
                ),
                "difficulty_mean": round(
                    mean(float(row["difficulty_avg"]) for row in items), 2
                ),
                "constraint_mean": round(
                    mean(float(row["constraint_avg"]) for row in items), 2
                ),
                "overall_mean": round(
                    mean(float(row["overall_avg"]) for row in items), 2
                ),
                "manual_review_candidates": sum(
                    row["needs_manual_check"] == "True" for row in items
                ),
                "modified_items": sum(row["modified"] == "True" for row in items),
            }
        )
    return rows


def build_pairwise_table(data_root: Path, judges: Sequence[JudgeSpec]) -> list[dict]:
    rows: list[dict] = []
    for judge in judges:
        stats: dict[str, dict[str, int | float]] = {}
        for language in LANGUAGES:
            records = latest_records(judge_root(data_root, language, judge) / "pairwise", "pairwise")
            valid = [record for record in records.values() if record.get("winner") != "error"]
            inconsistent_records = [
                record for record in valid if record.get("winner") == "inconsistent"
            ]
            inconsistent = len(inconsistent_records)
            same_first = sum(
                record.get("winner_ab") == "A" and record.get("winner_ba") == "A"
                for record in inconsistent_records
            )
            same_second = sum(
                record.get("winner_ab") == "B" and record.get("winner_ba") == "B"
                for record in inconsistent_records
            )
            other = inconsistent - same_first - same_second
            stats[language] = {
                "inconsistent": inconsistent,
                "valid": len(valid),
                "rate_pct": inconsistent / len(valid) * 100 if valid else float("nan"),
                "same_first": same_first,
                "same_first_pct": same_first / inconsistent * 100 if inconsistent else float("nan"),
                "same_second": same_second,
                "same_second_pct": same_second / inconsistent * 100 if inconsistent else float("nan"),
                "other": other,
                "other_pct": other / inconsistent * 100 if inconsistent else float("nan"),
            }
        rows.append(
            {
                "judge": judge.display,
                "en_inconsistent": stats["en"]["inconsistent"],
                "en_valid": stats["en"]["valid"],
                "en_rate_pct": round(float(stats["en"]["rate_pct"]), 2),
                "ko_inconsistent": stats["ko"]["inconsistent"],
                "ko_valid": stats["ko"]["valid"],
                "ko_rate_pct": round(float(stats["ko"]["rate_pct"]), 2),
                "delta_ko_minus_en_pp": round(
                    float(stats["ko"]["rate_pct"]) - float(stats["en"]["rate_pct"]),
                    2,
                ),
                "ko_same_first": stats["ko"]["same_first"],
                "ko_same_first_pct": round(float(stats["ko"]["same_first_pct"]), 2),
                "ko_same_second": stats["ko"]["same_second"],
                "ko_same_second_pct": round(float(stats["ko"]["same_second_pct"]), 2),
                "ko_other_inconsistent": stats["ko"]["other"],
                "ko_other_inconsistent_pct": round(float(stats["ko"]["other_pct"]), 2),
            }
        )
    rows.append(
        {
            "judge": "Mean",
            "en_inconsistent": "",
            "en_valid": "",
            "en_rate_pct": round(mean(float(row["en_rate_pct"]) for row in rows), 2),
            "ko_inconsistent": "",
            "ko_valid": "",
            "ko_rate_pct": round(mean(float(row["ko_rate_pct"]) for row in rows), 2),
            "delta_ko_minus_en_pp": round(
                mean(float(row["ko_rate_pct"]) for row in rows)
                - mean(float(row["en_rate_pct"]) for row in rows),
                2,
            ),
            "ko_same_first": "",
            "ko_same_first_pct": "",
            "ko_same_second": "",
            "ko_same_second_pct": "",
            "ko_other_inconsistent": "",
            "ko_other_inconsistent_pct": "",
        }
    )
    return rows


def single_model_scores(data_root: Path, language: str, judge: JudgeSpec) -> dict[str, list[float]]:
    records = latest_records(judge_root(data_root, language, judge) / "single_grade", "single_grade")
    scores: dict[str, list[float]] = defaultdict(list)
    for record in records.values():
        model_id = str(record["model_id"])
        for field in ("score_turn1", "score_turn2"):
            value = record.get(field)
            if valid_score(value):
                scores[model_id].append(float(value))
    return dict(scores)


def build_single_table(data_root: Path, judges: Sequence[JudgeSpec]) -> list[dict]:
    rows: list[dict] = []
    unrounded: list[tuple[float, float, float]] = []
    for judge in judges:
        stats: dict[str, tuple[float, int]] = {}
        for language in LANGUAGES:
            by_model = single_model_scores(data_root, language, judge)
            missing = set(MODEL_ORDER) - set(by_model)
            if missing:
                raise ValueError(f"{judge.display} {language}: missing model scores: {sorted(missing)}")
            valid_scores = [
                score
                for model in MODEL_ORDER
                for score in by_model[model]
            ]
            stats[language] = (
                mean(valid_scores),
                len(valid_scores),
            )
        delta = stats["ko"][0] - stats["en"][0]
        unrounded.append((stats["en"][0], stats["ko"][0], delta))
        rows.append(
            {
                "judge": judge.display,
                "en_mean": round(stats["en"][0], 2),
                "en_valid_scores": stats["en"][1],
                "ko_mean": round(stats["ko"][0], 2),
                "ko_valid_scores": stats["ko"][1],
                "delta_ko_minus_en": round(delta, 2),
            }
        )
    rows.append(
        {
            "judge": "Mean",
            "en_mean": round(mean(value[0] for value in unrounded), 2),
            "en_valid_scores": "",
            "ko_mean": round(mean(value[1] for value in unrounded), 2),
            "ko_valid_scores": "",
            "delta_ko_minus_en": round(mean(value[2] for value in unrounded), 2),
        }
    )
    return rows


def build_reference_table(data_root: Path, judges: Sequence[JudgeSpec]) -> list[dict]:
    rows: list[dict] = []
    unrounded: list[dict[str, tuple[float, float, float]]] = []
    for judge in judges:
        stats: dict[str, tuple[float, float, int]] = {}
        for language in LANGUAGES:
            root = judge_root(data_root, language, judge)
            standard = latest_records(root / "single_grade", "single_grade")
            reference = latest_records(root / "single_grade_ref", "single_grade_ref")
            paired: list[tuple[float, float]] = []
            for key in sorted(set(standard) & set(reference)):
                standard_score = standard[key].get("score_turn2")
                reference_score = reference[key].get("score_turn2")
                if valid_score(standard_score) and valid_score(reference_score):
                    paired.append((float(standard_score), float(reference_score)))
            stats[language] = (
                mean(value[0] for value in paired),
                mean(value[1] for value in paired),
                len(paired),
            )
        unrounded.append(
            {
                language: (
                    stats[language][0],
                    stats[language][1],
                    stats[language][1] - stats[language][0],
                )
                for language in LANGUAGES
            }
        )
        rows.append(
            {
                "judge": judge.display,
                "en_standard_mean": round(stats["en"][0], 2),
                "en_reference_mean": round(stats["en"][1], 2),
                "en_delta": round(stats["en"][1] - stats["en"][0], 2),
                "en_paired": stats["en"][2],
                "ko_standard_mean": round(stats["ko"][0], 2),
                "ko_reference_mean": round(stats["ko"][1], 2),
                "ko_delta": round(stats["ko"][1] - stats["ko"][0], 2),
                "ko_paired": stats["ko"][2],
            }
        )
    rows.append(
        {
            "judge": "Mean",
            "en_standard_mean": round(mean(value["en"][0] for value in unrounded), 2),
            "en_reference_mean": round(mean(value["en"][1] for value in unrounded), 2),
            "en_delta": round(mean(value["en"][2] for value in unrounded), 2),
            "en_paired": "",
            "ko_standard_mean": round(mean(value["ko"][0] for value in unrounded), 2),
            "ko_reference_mean": round(mean(value["ko"][1] for value in unrounded), 2),
            "ko_delta": round(mean(value["ko"][2] for value in unrounded), 2),
            "ko_paired": "",
        }
    )
    return rows


def classify_call(raw: object, parsed: object) -> str:
    if parsed not in {-1, -1.0, "error", None}:
        return "valid"
    if not isinstance(raw, str) or not raw.strip():
        return "empty_or_api"
    return "format_parse"


def build_failure_table(data_root: Path, judges: Sequence[JudgeSpec]) -> list[dict]:
    expected_records = {"single_grade": 480, "pairwise": 1200, "single_grade_ref": 174}
    rows: list[dict] = []
    for language in LANGUAGES:
        for judge in judges:
            root = judge_root(data_root, language, judge)
            for protocol in PROTOCOLS:
                records = latest_records(root / protocol, protocol)
                counts = defaultdict(int)
                for record in records.values():
                    if protocol == "pairwise":
                        calls = (
                            (record.get("judgment_ab"), record.get("winner_ab")),
                            (record.get("judgment_ba"), record.get("winner_ba")),
                        )
                    elif protocol == "single_grade_ref":
                        calls = ((record.get("judgment_turn2"), record.get("score_turn2")),)
                    else:
                        calls = (
                            (record.get("judgment_turn1"), record.get("score_turn1")),
                            (record.get("judgment_turn2"), record.get("score_turn2")),
                        )
                    for raw, parsed in calls:
                        counts[classify_call(raw, parsed)] += 1
                calls_per_record = 1 if protocol == "single_grade_ref" else 2
                expected_calls = expected_records[protocol] * calls_per_record
                missing_calls = max(expected_calls - sum(counts.values()), 0)
                rows.append(
                    {
                        "language": language,
                        "judge": judge.display,
                        "protocol": protocol,
                        "expected_calls": expected_calls,
                        "valid_calls": counts["valid"],
                        "format_parse_failures": counts["format_parse"],
                        "empty_or_api_failures": counts["empty_or_api"],
                        "missing_calls": missing_calls,
                        "total_failures": counts["format_parse"]
                        + counts["empty_or_api"]
                        + missing_calls,
                    }
                )
    return rows


def build_figure_rows(data_root: Path, judges: Sequence[JudgeSpec]) -> list[dict]:
    questions = {
        language: {
            int(row["question_id"]): str(row["category"])
            for row in read_jsonl(data_root / language / "questions.jsonl")
        }
        for language in LANGUAGES
    }
    rows: list[dict] = []
    for language in LANGUAGES:
        scores_by_judge: dict[str, dict[str, list[float]]] = {}
        category_scores_by_judge: dict[str, dict[str, list[float]]] = {}
        for judge in judges:
            records = latest_records(
                judge_root(data_root, language, judge) / "single_grade", "single_grade"
            )
            model_values: dict[str, list[float]] = defaultdict(list)
            category_values: dict[str, list[float]] = defaultdict(list)
            for record in records.values():
                model_id = str(record["model_id"])
                category = questions[language][int(record["question_id"])]
                for field in ("score_turn1", "score_turn2"):
                    value = record.get(field)
                    if valid_score(value):
                        model_values[model_id].append(float(value))
                        category_values[category].append(float(value))
            scores_by_judge[judge.key] = dict(model_values)
            category_scores_by_judge[judge.key] = dict(category_values)

        for row_type, identifiers, display_map, source in (
            ("model", MODEL_ORDER, MODEL_DISPLAY, scores_by_judge),
            ("category", CATEGORY_ORDER, {value: value for value in CATEGORY_ORDER}, category_scores_by_judge),
        ):
            for row_order, identifier in enumerate(identifiers):
                values = {
                    judge.key: mean(source[judge.key][identifier])
                    for judge in judges
                }
                row = {
                    "language": language,
                    "row_type": row_type,
                    "row_order": row_order,
                    "row_id": identifier,
                    "row_label": display_map[identifier],
                }
                row.update({key: round(value, 4) for key, value in values.items()})
                row["judge_mean"] = round(mean(values.values()), 4)
                rows.append(row)
    return rows


def render_figure(rows: Sequence[dict], judges: Sequence[JudgeSpec], output_dir: Path) -> None:
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib import font_manager

    output_dir.mkdir(parents=True, exist_ok=True)
    columns = [judge.key for judge in judges] + ["judge_mean"]
    labels = [judge.figure_display for judge in judges] + [f"{len(judges)}인\n평균"]
    category_labels = {
        "writing": "쓰기",
        "roleplay": "역할극",
        "extraction": "정보 추출",
        "reasoning": "추론",
        "math": "수학",
        "coding": "코딩",
        "stem": "STEM",
        "humanities": "인문학",
    }
    panels = (
        ("en", "model", "(a) 생성 모델별 영어 점수"),
        ("ko", "model", "(b) 생성 모델별 한국어 점수"),
        ("en", "category", "(c) 범주별 영어 점수"),
        ("ko", "category", "(d) 범주별 한국어 점수"),
    )
    font_path = None
    for font_name in (
        "Apple SD Gothic Neo",
        "Noto Sans CJK KR",
        "Noto Sans KR",
        "NanumGothic",
        "Malgun Gothic",
        "Arial Unicode MS",
    ):
        try:
            font_path = font_manager.findfont(font_name, fallback_to_default=False)
            break
        except ValueError:
            continue
    regular_font = font_manager.FontProperties(fname=font_path)
    bold_font = font_manager.FontProperties(fname=font_path, weight="bold")
    figure, axes = plt.subplots(
        2,
        2,
        figsize=(FIGURE_WIDTH_INCHES, FIGURE_HEIGHT_INCHES),
        constrained_layout=False,
    )
    image = None
    for axis, (language, row_type, title) in zip(axes.ravel(), panels):
        panel_rows = sorted(
            (
                row
                for row in rows
                if row["language"] == language and row["row_type"] == row_type
            ),
            key=lambda row: int(row["row_order"]),
        )
        matrix = np.asarray(
            [[float(row[column]) for column in columns] for row in panel_rows],
            dtype=float,
        )
        image = axis.imshow(matrix, cmap="YlGnBu", vmin=1, vmax=10, aspect="auto")
        axis.set_title(title, fontproperties=bold_font, fontsize=7.2, pad=2.5)
        axis.set_xticks(
            range(len(labels)),
            labels,
            fontproperties=regular_font,
            fontsize=5.2,
        )
        axis.tick_params(length=0, pad=1.5)
        axis.set_yticks(
            range(len(panel_rows)),
            [
                category_labels.get(str(row["row_id"]), str(row["row_label"]))
                for row in panel_rows
            ],
            fontproperties=regular_font,
            fontsize=5.2,
        )
        axis.set_xticks(np.arange(-0.5, len(columns), 1), minor=True)
        axis.set_yticks(np.arange(-0.5, len(panel_rows), 1), minor=True)
        axis.grid(which="minor", color="white", linewidth=0.65)
        axis.tick_params(which="minor", bottom=False, left=False)
        axis.axvline(len(judges) - 0.5, color="#202020", linewidth=1.25)
        for x_index, label in enumerate(axis.get_xticklabels()):
            if x_index == len(labels) - 1:
                label.set_fontweight("bold")
        for y_index in range(matrix.shape[0]):
            for x_index in range(matrix.shape[1]):
                value = matrix[y_index, x_index]
                red, green, blue, _ = image.cmap(image.norm(value))
                luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
                axis.text(
                    x_index,
                    y_index,
                    f"{value:.2f}",
                    ha="center",
                    va="center",
                    fontsize=4.8,
                    fontproperties=(
                        bold_font if x_index == len(columns) - 1 else regular_font
                    ),
                    color="white" if luminance < 0.52 else "#111111",
                )
        for spine in axis.spines.values():
            spine.set_visible(False)

    if image is None:
        raise ValueError("no data for Figure 3")
    figure.subplots_adjust(
        left=0.105,
        right=0.990,
        top=0.950,
        bottom=0.205,
        wspace=0.25,
        hspace=0.40,
    )
    color_axis = figure.add_axes((0.30, 0.065, 0.42, 0.020))
    colorbar = figure.colorbar(image, cax=color_axis, orientation="horizontal")
    colorbar.set_label(
        "일반 단일 채점 평균(1–10점)",
        fontproperties=regular_font,
        fontsize=5.6,
        labelpad=2,
    )
    colorbar.ax.xaxis.set_label_position("top")
    colorbar.set_ticks(range(1, 11))
    colorbar.ax.tick_params(labelsize=4.8, length=2, pad=1)
    for tick_label in colorbar.ax.get_xticklabels():
        tick_label.set_fontproperties(regular_font)
    output_stem = "figure3_single_scores"
    figure.savefig(
        output_dir / f"{output_stem}.png",
        dpi=320,
        facecolor="white",
        bbox_inches=None,
        pad_inches=0,
    )
    figure.savefig(
        output_dir / f"{output_stem}.pdf",
        facecolor="white",
        bbox_inches=None,
        pad_inches=0,
        metadata={
            "Creator": "Korean MT-Bench artifact builder",
            "CreationDate": None,
            "ModDate": None,
        },
    )
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data")
    parser.add_argument("--results-dir", type=Path, default=ROOT / "data" / "results")
    parser.add_argument(
        "--figure-dir",
        type=Path,
        default=ROOT / "generated" / "figures",
        help="local, git-ignored output directory for Figure 3",
    )
    parser.add_argument("--no-figure", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_root = args.data_root.resolve()
    judges = active_judges(data_root)
    if len(judges) != 6:
        raise ValueError(f"expected six judges, found {len(judges)}")

    outputs = (
        (
            "table4_translation_review.csv",
            (
                "category",
                "n",
                "bleu_mean",
                "semantic_mean",
                "difficulty_mean",
                "constraint_mean",
                "overall_mean",
                "manual_review_candidates",
                "modified_items",
            ),
            build_translation_review(data_root),
        ),
        (
            "table5_pairwise_inconsistency.csv",
            (
                "judge",
                "en_inconsistent",
                "en_valid",
                "en_rate_pct",
                "ko_inconsistent",
                "ko_valid",
                "ko_rate_pct",
                "delta_ko_minus_en_pp",
                "ko_same_first",
                "ko_same_first_pct",
                "ko_same_second",
                "ko_same_second_pct",
                "ko_other_inconsistent",
                "ko_other_inconsistent_pct",
            ),
            build_pairwise_table(data_root, judges),
        ),
        (
            "table6_single_scores.csv",
            (
                "judge",
                "en_mean",
                "en_valid_scores",
                "ko_mean",
                "ko_valid_scores",
                "delta_ko_minus_en",
            ),
            build_single_table(data_root, judges),
        ),
        (
            "table7_reference_scores.csv",
            (
                "judge",
                "en_standard_mean",
                "en_reference_mean",
                "en_delta",
                "en_paired",
                "ko_standard_mean",
                "ko_reference_mean",
                "ko_delta",
                "ko_paired",
            ),
            build_reference_table(data_root, judges),
        ),
        (
            "table8_parse_failures.csv",
            (
                "language",
                "judge",
                "protocol",
                "expected_calls",
                "valid_calls",
                "format_parse_failures",
                "empty_or_api_failures",
                "missing_calls",
                "total_failures",
            ),
            build_failure_table(data_root, judges),
        ),
    )
    for filename, fieldnames, rows in outputs:
        output = args.results_dir / filename
        write_csv(output, fieldnames, rows)
        print(f"[OK] wrote {output} ({len(rows)} rows)")

    figure_rows = build_figure_rows(data_root, judges)
    figure_fields = (
        "language",
        "row_type",
        "row_order",
        "row_id",
        "row_label",
        *(judge.key for judge in judges),
        "judge_mean",
    )
    figure_data = args.results_dir / "figure3_scores.csv"
    write_csv(figure_data, figure_fields, figure_rows)
    print(f"[OK] wrote {figure_data} ({len(figure_rows)} rows)")
    if not args.no_figure:
        render_figure(figure_rows, judges, args.figure_dir)
        print(f"[OK] wrote {args.figure_dir / 'figure3_single_scores.png'}")
        print(f"[OK] wrote {args.figure_dir / 'figure3_single_scores.pdf'}")


if __name__ == "__main__":
    main()
