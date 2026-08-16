import json
import tempfile
import unittest
from pathlib import Path

from mtbench_repro.aggregate import (
    _resolve_expected_reference_ids,
    compute_reference_scores,
    compute_single_scores,
    compute_win_rates,
)
from mtbench_repro.schemas import MTBenchQuestion


def _write_jsonl(path: Path, records) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def _single(
    question_id,
    score1,
    score2,
    tstamp,
    model="model-a",
    judge="judge-a",
    category="writing",
):
    return {
        "question_id": question_id,
        "model_id": model,
        "judge_id": judge,
        "score_turn1": score1,
        "score_turn2": score2,
        "judgment_turn1": "raw-1",
        "judgment_turn2": "raw-2",
        "category": category,
        "tstamp": tstamp,
    }


def _pairwise(question_id, winner, tstamp, judge="judge-a"):
    verdicts = {
        "model-a": ("A", "B"),
        "model-b": ("B", "A"),
        "tie": ("tie", "tie"),
        "inconsistent": ("A", "A"),
        "error": ("error", "A"),
    }
    winner_ab, winner_ba = verdicts[winner]
    return {
        "question_id": question_id,
        "model_a": "model-a",
        "model_b": "model-b",
        "judge_id": judge,
        "winner": winner,
        "judgment_ab": "raw-ab",
        "judgment_ba": "raw-ba",
        "winner_ab": winner_ab,
        "winner_ba": winner_ba,
        "turn": 2,
        "category": "writing",
        "tstamp": tstamp,
    }


class AggregateDeduplicationTest(unittest.TestCase):
    def test_reference_auto_detection_accepts_historical_and_v3_sets(self):
        questions = [
            MTBenchQuestion(1, "math", ["q1", "q2"], ["r1", ""]),
            MTBenchQuestion(2, "math", ["q1", "q2"], ["r1", "r2"]),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ref_dir = root / "single_grade_ref"
            _write_jsonl(
                ref_dir / "model-a.jsonl",
                [
                    _single(1, -1, 5, 1, category="math"),
                    _single(2, -1, 5, 1, category="math"),
                ],
            )
            historical = _resolve_expected_reference_ids(
                questions, str(root), ["model-a"], "auto", False
            )
            self.assertEqual(historical, {1, 2})

            _write_jsonl(
                ref_dir / "model-a.jsonl",
                [_single(2, -1, 5, 1, category="math")],
            )
            current = _resolve_expected_reference_ids(
                questions, str(root), ["model-a"], "auto", False
            )
            self.assertEqual(current, {2})

    def test_invalid_single_score_is_rejected_at_load_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            grade_dir = root / "single_grade"
            _write_jsonl(
                grade_dir / "model-a.jsonl",
                [_single(1, 99, False, 1.0)],
            )

            with self.assertRaisesRegex(ValueError, "Invalid single judgment"):
                compute_single_scores(str(root))

    def test_internally_inconsistent_pairwise_row_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pairwise_dir = root / "pairwise"
            row = _pairwise(1, "model-a", 1.0)
            row["winner_ba"] = "A"
            _write_jsonl(pairwise_dir / "model-a_vs_model-b.jsonl", [row])

            with self.assertRaisesRegex(ValueError, "Invalid pairwise judgment"):
                compute_win_rates(str(root))

    def test_error_does_not_mask_invalid_raw_pairwise_verdict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pairwise_dir = root / "pairwise"
            row = _pairwise(1, "error", 1.0)
            row["winner_ba"] = "garbage"
            _write_jsonl(pairwise_dir / "model-a_vs_model-b.jsonl", [row])

            with self.assertRaisesRegex(ValueError, "Invalid pairwise judgment"):
                compute_win_rates(str(root))

    def test_single_copy_file_is_deduplicated_and_denominators_are_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            grade_dir = root / "single_grade"
            original = [_single(1, 1.0, 3.0, 1.0), _single(2, 5.0, -1.0, 1.0)]
            duplicate = [_single(1, 7.0, 9.0, 2.0)]
            _write_jsonl(grade_dir / "model-a.jsonl", original)
            _write_jsonl(grade_dir / "model-a 2.jsonl", duplicate)

            result = compute_single_scores(
                str(root), expected_questions=2, allow_partial=False
            )["model-a"]

            self.assertEqual(result["n_questions"], 2.0)
            self.assertEqual(result["n_observed_samples"], 4.0)
            self.assertEqual(result["n_expected_samples"], 4.0)
            self.assertEqual(result["n_samples"], 3.0)
            self.assertEqual(result["n_parse_failures"], 1.0)
            self.assertAlmostEqual(result["parse_failure_rate"], 0.25)
            self.assertAlmostEqual(result["overall"], 7.0)

    def test_reference_uses_only_turn2_and_deduplicates_latest_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            grade_dir = root / "single_grade_ref"
            _write_jsonl(
                grade_dir / "model-a.jsonl",
                [_single(1, -1.0, 2.0, 1.0), _single(2, -1.0, -1.0, 1.0)],
            )
            _write_jsonl(
                grade_dir / "model-a 2.jsonl", [_single(1, -1.0, 8.0, 2.0)]
            )

            result = compute_reference_scores(
                str(root), expected_questions=2, allow_partial=False
            )["model-a"]

            self.assertEqual(result["n_questions"], 2.0)
            self.assertEqual(result["n_observed_samples"], 2.0)
            self.assertEqual(result["n_samples"], 1.0)
            self.assertEqual(result["n_parse_failures"], 1.0)
            self.assertAlmostEqual(result["overall"], 8.0)

    def test_pairwise_reports_official_and_consistent_only_win_rates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pairwise_dir = root / "pairwise"
            original = [
                _pairwise(1, "model-a", 1.0),
                _pairwise(2, "inconsistent", 1.0),
                _pairwise(3, "error", 1.0),
                _pairwise(4, "tie", 1.0),
            ]
            _write_jsonl(pairwise_dir / "model-a_vs_model-b.jsonl", original)
            _write_jsonl(
                pairwise_dir / "model-a_vs_model-b 2.jsonl",
                [_pairwise(1, "model-a", 1.0)],
            )

            result = compute_win_rates(str(root))

            self.assertEqual(result["model-a"]["n_pairs_total"], 4.0)
            self.assertEqual(result["model-a"]["n_games"], 3.0)
            self.assertEqual(result["model-a"]["n_consistent_games"], 2.0)
            self.assertEqual(result["model-a"]["n_inconsistent"], 1.0)
            self.assertEqual(result["model-a"]["n_errors"], 1.0)
            self.assertAlmostEqual(result["model-a"]["overall"], 2.0 / 3.0)
            self.assertAlmostEqual(result["model-b"]["overall"], 1.0 / 3.0)
            self.assertAlmostEqual(
                result["model-a"]["overall_consistent_only"], 0.75
            )
            self.assertAlmostEqual(
                result["model-b"]["overall_consistent_only"], 0.25
            )

    def test_single_rejects_mixed_judges(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            grade_dir = root / "single_grade"
            _write_jsonl(
                grade_dir / "model-a.jsonl",
                [
                    _single(1, 1.0, 1.0, 1.0, judge="judge-a"),
                    _single(2, 10.0, 10.0, 1.0, judge="judge-b"),
                ],
            )
            with self.assertRaisesRegex(ValueError, "multiple judge_id"):
                compute_single_scores(str(root))

    def test_single_rejects_missing_id_even_when_extra_id_keeps_same_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            grade_dir = root / "single_grade"
            _write_jsonl(
                grade_dir / "model-a.jsonl",
                [_single(1, 5.0, 5.0, 1.0), _single(99, 5.0, 5.0, 1.0)],
            )

            with self.assertRaisesRegex(
                ValueError, r"missing=\[2\].*unexpected=\[99\]"
            ):
                compute_single_scores(
                    str(root),
                    expected_question_ids={1, 2},
                )

    def test_reference_incomplete_coverage_is_an_error_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            grade_dir = root / "single_grade_ref"
            _write_jsonl(
                grade_dir / "model-a.jsonl",
                [_single(1, -1.0, 5.0, 1.0)],
            )

            with self.assertRaisesRegex(ValueError, "Incomplete reference-guided"):
                compute_reference_scores(
                    str(root),
                    model_ids=["model-a"],
                    expected_question_ids={1, 2},
                )

    def test_pairwise_rejects_mixed_judges(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pairwise_dir = root / "pairwise"
            _write_jsonl(
                pairwise_dir / "model-a_vs_model-b.jsonl",
                [
                    _pairwise(1, "model-a", 1.0, judge="judge-a"),
                    _pairwise(2, "model-b", 1.0, judge="judge-b"),
                ],
            )
            with self.assertRaisesRegex(ValueError, "multiple judge_id"):
                compute_win_rates(str(root))

    def test_pairwise_requires_every_question_for_every_model_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pairwise_dir = root / "pairwise"
            _write_jsonl(
                pairwise_dir / "model-a_vs_model-b.jsonl",
                [_pairwise(1, "model-a", 1.0)],
            )

            with self.assertRaisesRegex(ValueError, "Incomplete pairwise coverage"):
                compute_win_rates(
                    str(root),
                    model_ids=["model-a", "model-b"],
                    expected_question_ids={1, 2},
                )

            partial = compute_win_rates(
                str(root),
                model_ids=["model-a", "model-b"],
                expected_question_ids={1, 2},
                allow_partial=True,
            )
            self.assertEqual(partial["model-a"]["n_pairs_total"], 1.0)
            self.assertEqual(partial["model-a"]["n_expected_pairs"], 2.0)


if __name__ == "__main__":
    unittest.main()
