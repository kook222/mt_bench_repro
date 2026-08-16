import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "scripts" / "translate" / "back_translate.py"
SPEC = importlib.util.spec_from_file_location("back_translate", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

VALIDITY_SCRIPT = (
    Path(__file__).parents[1]
    / "scripts"
    / "analysis"
    / "analyze_translation_validity.py"
)
VALIDITY_SPEC = importlib.util.spec_from_file_location(
    "analyze_translation_validity", VALIDITY_SCRIPT
)
VALIDITY = importlib.util.module_from_spec(VALIDITY_SPEC)
assert VALIDITY_SPEC.loader is not None
VALIDITY_SPEC.loader.exec_module(VALIDITY)


class BackTranslationResumeTest(unittest.TestCase):
    def test_fingerprint_changes_when_a_constraint_changes(self):
        question = {
            "question_id": 83,
            "category": "writing",
            "turns": ["200단어 이내로 작성하세요.", "다시 작성하세요."],
        }
        original = MODULE.question_fingerprint(question)
        question["turns"][0] = "200글자 이내로 작성하세요."

        self.assertNotEqual(original, MODULE.question_fingerprint(question))

    def test_prompt_protocol_has_a_stable_fingerprint(self):
        fingerprint = MODULE.prompt_fingerprint()

        self.assertEqual(len(fingerprint), 64)
        self.assertEqual(fingerprint, MODULE.prompt_fingerprint())

    def test_mock_back_translation_is_not_resumed_as_live(self):
        question = {
            "question_id": 83,
            "category": "writing",
            "turns": ["first", "second"],
        }
        record = {
            "source_sha256": MODULE.question_fingerprint(question),
            "back_translation_provider": "openai",
            "back_translation_model": "model",
            "back_translation_prompt_sha256": MODULE.prompt_fingerprint(),
            "back_translation_mode": "mock",
            "turns": ["first", "second"],
        }
        self.assertTrue(
            MODULE.record_is_current(record, question, "openai", "model", "mock")
        )
        self.assertFalse(
            MODULE.record_is_current(record, question, "openai", "model", "live")
        )

        record["turns"] = []
        self.assertFalse(
            MODULE.record_is_current(record, question, "openai", "model", "mock")
        )

    def test_mock_validity_score_is_not_resumed_as_live(self):
        original = {"question_id": 1, "category": "writing", "turns": ["a", "b"]}
        korean = {"question_id": 1, "category": "writing", "turns": ["가", "나"]}
        back = {"question_id": 1, "category": "writing", "turns": ["a", "b"]}
        row = {
            "question_id": "1",
            "category": "writing",
            "original_sha256": VALIDITY.record_fingerprint(original),
            "korean_source_sha256": VALIDITY.record_fingerprint(korean),
            "back_translation_sha256": VALIDITY.record_fingerprint(back),
            "validity_provider": "openai",
            "validity_model": "model",
            "validity_prompt_sha256": VALIDITY.validity_prompt_fingerprint(),
            "validity_mode": "mock",
            "parse_status_turn1": "ok: mock",
            "parse_status_turn2": "ok: mock",
            "bleu_turn1": "1.0",
            "bleu_turn2": "1.0",
            "bleu_avg": "1.0",
            "semantic_turn1": "4",
            "semantic_turn2": "4",
            "semantic_avg": "4.0",
            "difficulty_turn1": "4",
            "difficulty_turn2": "4",
            "difficulty_avg": "4.0",
            "constraint_turn1": "4",
            "constraint_turn2": "4",
            "constraint_avg": "4.0",
            "overall_turn1": "4",
            "overall_turn2": "4",
            "overall_avg": "4.0",
            "needs_manual_check": "False",
            "issue_summary_turn1": "mock",
            "issue_summary_turn2": "mock",
        }
        self.assertTrue(
            VALIDITY.validity_record_is_current(
                row, original, korean, back, "openai", "model", "mock"
            )
        )
        self.assertFalse(
            VALIDITY.validity_record_is_current(
                row, original, korean, back, "openai", "model", "live"
            )
        )

        for field, bad_value in (
            ("semantic_turn1", ""),
            ("overall_turn2", "99"),
            ("needs_manual_check", "garbage"),
            ("bleu_avg", "NaN"),
        ):
            with self.subTest(field=field):
                malformed = dict(row)
                malformed[field] = bad_value
                self.assertFalse(
                    VALIDITY.validity_record_is_current(
                        malformed,
                        original,
                        korean,
                        back,
                        "openai",
                        "model",
                        "mock",
                    )
                )

    def test_validity_rejects_wrong_back_translation_prompt_hash(self):
        korean = {"question_id": 1, "category": "writing", "turns": ["가", "나"]}
        back = {
            "question_id": 1,
            "category": "writing",
            "turns": ["a", "b"],
            "source_sha256": VALIDITY.record_fingerprint(korean),
            "back_translation_prompt_sha256": "0" * 64,
        }

        self.assertFalse(
            VALIDITY.back_translation_record_is_current(back, korean, "mock")
        )
        back["back_translation_prompt_sha256"] = MODULE.prompt_fingerprint()
        self.assertTrue(
            VALIDITY.back_translation_record_is_current(back, korean, "mock")
        )


class StrictValidityParsingTest(unittest.TestCase):
    @staticmethod
    def _response(**overrides):
        payload = {
            "semantic_preservation": 5,
            "difficulty_preservation": 5,
            "constraint_preservation": 5,
            "overall_score": 5,
            "issue_summary": "no issue",
            "needs_manual_check": False,
        }
        payload.update(overrides)
        return json.dumps(payload)

    def test_boolean_is_not_accepted_as_integer_score(self):
        result = VALIDITY.parse_validity_response(
            self._response(semantic_preservation=True)
        )

        self.assertEqual(result["semantic_preservation"], -1)
        self.assertTrue(result["needs_manual_check"])
        self.assertIn("integer from 1 through 5", result["parse_status"])

    def test_out_of_range_and_non_integer_scores_are_rejected(self):
        for value in (0, 6, 4.0, "4"):
            with self.subTest(value=value):
                result = VALIDITY.parse_validity_response(
                    self._response(overall_score=value)
                )
                self.assertEqual(result["overall_score"], -1)
                self.assertTrue(result["needs_manual_check"])

    def test_string_is_not_accepted_as_boolean(self):
        result = VALIDITY.parse_validity_response(
            self._response(needs_manual_check="false")
        )

        self.assertEqual(result["overall_score"], -1)
        self.assertTrue(result["needs_manual_check"])
        self.assertIn("JSON boolean", result["parse_status"])

    def test_low_score_forces_manual_check(self):
        result = VALIDITY.parse_validity_response(
            self._response(constraint_preservation=3, needs_manual_check=False)
        )

        self.assertEqual(result["constraint_preservation"], 3)
        self.assertTrue(result["needs_manual_check"])
        self.assertIn("forced", result["parse_status"])

    def test_surrounding_prose_is_rejected(self):
        result = VALIDITY.parse_validity_response(
            f"Here is the result: {self._response()}"
        )

        self.assertTrue(result["needs_manual_check"])
        self.assertTrue(result["parse_status"].startswith("invalid:"))


class TranslationPipelineTransactionTest(unittest.TestCase):
    @staticmethod
    def _questions(prefix: str) -> list[dict]:
        return [
            {
                "question_id": question_id,
                "category": "writing",
                "turns": [
                    f"{prefix}-{question_id}-turn-1",
                    f"{prefix}-{question_id}-turn-2",
                ],
            }
            for question_id in range(81, 161)
        ]

    @staticmethod
    def _write_jsonl(path: Path, records: list[dict]) -> None:
        path.write_text(
            "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
            encoding="utf-8",
        )

    def test_validity_requires_identical_80_item_two_turn_coverage(self):
        original = {q["question_id"]: q for q in self._questions("en")}
        korean = {q["question_id"]: q for q in self._questions("ko")}
        back = {q["question_id"]: q for q in self._questions("back")}

        self.assertEqual(
            len(VALIDITY.validate_input_coverage(original, korean, back)), 80
        )
        del back[160]
        with self.assertRaisesRegex(ValueError, "exactly 80"):
            VALIDITY.validate_input_coverage(original, korean, back)

        back = {q["question_id"]: q for q in self._questions("back")}
        back[100]["turns"] = ["only one turn"]
        with self.assertRaisesRegex(ValueError, "exactly 2"):
            VALIDITY.validate_input_coverage(original, korean, back)

    def test_back_translation_no_resume_preserves_old_output_on_failure(self):
        questions = self._questions("ko")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "questions.jsonl"
            output_path = root / "questions_back.jsonl"
            self._write_jsonl(input_path, questions)
            output_path.write_text("old output\n", encoding="utf-8")

            def translate(_client, question, _model, _sleep):
                if question["question_id"] == 120:
                    raise RuntimeError("simulated API failure")
                return dict(question)

            argv = [
                "back_translate.py",
                "--input",
                str(input_path),
                "--output",
                str(output_path),
                "--mock",
                "--no-resume",
                "--sleep",
                "0",
            ]
            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(MODULE, "back_translate_question", side_effect=translate),
                redirect_stdout(io.StringIO()),
                self.assertRaises(SystemExit) as raised,
            ):
                MODULE.main()

            self.assertEqual(raised.exception.code, 1)
            self.assertEqual(output_path.read_text(encoding="utf-8"), "old output\n")

    def test_validity_no_resume_preserves_outputs_on_invalid_score(self):
        original = self._questions("en")
        korean = self._questions("ko")
        back = []
        for source, translated in zip(korean, self._questions("back")):
            translated.update(
                {
                    "source_sha256": VALIDITY.record_fingerprint(source),
                    "back_translation_prompt_sha256": MODULE.prompt_fingerprint(),
                    "back_translation_mode": "mock",
                }
            )
            back.append(translated)

        valid = VALIDITY.parse_validity_response(StrictValidityParsingTest._response())
        invalid = VALIDITY.parse_validity_response("not JSON")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original_path = root / "original.jsonl"
            korean_path = root / "korean.jsonl"
            back_path = root / "back.jsonl"
            output_path = root / "validity.csv"
            category_path = root / "validity_category.csv"
            self._write_jsonl(original_path, original)
            self._write_jsonl(korean_path, korean)
            self._write_jsonl(back_path, back)
            output_path.write_text("old validity\n", encoding="utf-8")
            category_path.write_text("old category\n", encoding="utf-8")

            call_count = 0

            def score(*_args, **_kwargs):
                nonlocal call_count
                call_count += 1
                return invalid if call_count == 79 else valid

            argv = [
                "analyze_translation_validity.py",
                "--original",
                str(original_path),
                "--korean-source",
                str(korean_path),
                "--back-translated",
                str(back_path),
                "--output-csv",
                str(output_path),
                "--output-category-csv",
                str(category_path),
                "--mock",
                "--no-resume",
                "--sleep",
                "0",
            ]
            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(VALIDITY, "llm_validity_score", side_effect=score),
                redirect_stdout(io.StringIO()),
                self.assertRaises(SystemExit) as raised,
            ):
                VALIDITY.main()

            self.assertEqual(raised.exception.code, 1)
            self.assertEqual(output_path.read_text(encoding="utf-8"), "old validity\n")
            self.assertEqual(
                category_path.read_text(encoding="utf-8"), "old category\n"
            )


if __name__ == "__main__":
    unittest.main()
