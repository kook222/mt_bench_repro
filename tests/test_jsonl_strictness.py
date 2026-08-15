import json
import tempfile
import unittest
from pathlib import Path

from mtbench_repro.io_utils import load_questions, read_jsonl, write_jsonl
from mtbench_repro.schemas import JudgmentSingle


class JsonlStrictnessTest(unittest.TestCase):
    def test_parse_failure_average_serializes_as_json_null(self):
        judgment = JudgmentSingle(
            question_id=81,
            model_id="model",
            judge_id="judge",
            score_turn1=-1.0,
            score_turn2=5.0,
            judgment_turn1="unparsed",
            judgment_turn2="[[5]]",
        )

        payload = json.dumps(judgment.to_dict(), allow_nan=False)

        self.assertIsNone(json.loads(payload)["avg_score"])

    def test_writer_and_reader_reject_nonstandard_nan(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.jsonl"
            with self.assertRaises(ValueError):
                write_jsonl(path, [{"question_id": 81, "score": float("nan")}])

            path.write_text('{"question_id": 81, "score": NaN}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non-standard JSON"):
                list(read_jsonl(path))

    def test_question_loader_rejects_malformed_and_duplicate_units(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "questions.jsonl"
            valid = {
                "question_id": 81,
                "category": "writing",
                "turns": ["first", "second"],
            }
            path.write_text(json.dumps(valid) + "\nnot-json\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Invalid strict JSON"):
                load_questions(path)

            row = {
                "question_id": 81,
                "category": "writing",
                "turns": ["first", "second"],
            }
            path.write_text(
                json.dumps(row) + "\n" + json.dumps(row) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Duplicate question_id"):
                load_questions(path)

            path.write_text('{"question_id": 81}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Invalid question record"):
                load_questions(path)

    def test_question_loader_requires_exactly_two_nonempty_turns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "questions.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "question_id": 81,
                        "category": "writing",
                        "turns": ["only one"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "two nonempty turns"):
                load_questions(path)

    def test_public_question_sets_load_with_legacy_empty_reference_slots(self):
        root = Path(__file__).parents[1]
        for relative_path in (
            "data/en/questions.jsonl",
            "data/ko/questions.jsonl",
        ):
            with self.subTest(path=relative_path):
                questions = load_questions(root / relative_path)
                self.assertEqual(len(questions), 80)
                self.assertEqual(
                    [question.question_id for question in questions],
                    list(range(81, 161)),
                )

    def test_legacy_reference_slots_report_turn_availability(self):
        root = Path(__file__).parents[1]
        questions = {
            question.question_id: question
            for question in load_questions(root / "data/en/questions.jsonl")
        }

        self.assertTrue(questions[103].has_reference_for_turn(0))
        self.assertFalse(questions[103].has_reference_for_turn(1))
        self.assertFalse(questions[133].has_reference_for_turn(0))
        self.assertTrue(questions[133].has_reference_for_turn(1))


if __name__ == "__main__":
    unittest.main()
