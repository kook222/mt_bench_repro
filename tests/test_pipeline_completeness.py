import json
import tempfile
import unittest
from pathlib import Path

from mtbench_repro.client import ChatClient
from mtbench_repro.generate import run_generation
from mtbench_repro.judge_pairwise import run_judge_pairwise
from mtbench_repro.judge_reference import run_judge_reference_single
from mtbench_repro.judge_single import run_judge_single


def _write_jsonl(path: Path, records) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def _question(reference=None):
    record = {
        "question_id": 81,
        "category": "math" if reference else "writing",
        "turns": ["first", "second"],
    }
    if reference is not None:
        record["reference"] = reference
    return record


class PipelineCompletenessTest(unittest.TestCase):
    def test_generation_resume_prunes_stale_question_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            questions = root / "questions.jsonl"
            answers = root / "answers"
            _write_jsonl(questions, [_question()])
            client = ChatClient.mock()
            run_generation(
                str(questions),
                str(answers),
                "model-a",
                client,
                sleep_between_calls=0,
            )
            answer_path = answers / "model-a.jsonl"
            rows = [json.loads(line) for line in answer_path.read_text().splitlines()]
            stale = {**rows[0], "question_id": 999}
            _write_jsonl(answer_path, [rows[0], stale])

            run_generation(
                str(questions),
                str(answers),
                "model-a",
                client,
                sleep_between_calls=0,
            )

            final_rows = [
                json.loads(line) for line in answer_path.read_text().splitlines()
            ]
            self.assertEqual([row["question_id"] for row in final_rows], [81])

    def test_generation_api_failure_is_nonzero_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            questions = root / "questions.jsonl"
            _write_jsonl(questions, [_question()])
            client = ChatClient.mock()

            def fail(*_args, **_kwargs):
                raise RuntimeError("provider unavailable")

            client.chat = fail
            with self.assertRaisesRegex(RuntimeError, "Generation incomplete"):
                run_generation(
                    str(questions),
                    str(root / "answers"),
                    "model-a",
                    client,
                    sleep_between_calls=0,
                )

    def test_allow_partial_drops_stale_generation_record_after_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            questions = root / "questions.jsonl"
            answers = root / "answers"
            _write_jsonl(questions, [_question()])
            client = ChatClient.mock()
            run_generation(
                str(questions),
                str(answers),
                "model-a",
                client,
                sleep_between_calls=0,
            )

            changed = _question()
            changed["turns"][0] = "changed first turn"
            _write_jsonl(questions, [changed])

            def fail(*_args, **_kwargs):
                raise RuntimeError("provider unavailable")

            client.chat = fail
            run_generation(
                str(questions),
                str(answers),
                "model-a",
                client,
                sleep_between_calls=0,
                allow_partial=True,
            )

            self.assertEqual(
                (answers / "model-a.jsonl").read_text(encoding="utf-8"), ""
            )

    def test_single_missing_answer_is_nonzero_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            questions = root / "questions.jsonl"
            answers = root / "answers"
            _write_jsonl(questions, [_question()])
            _write_jsonl(answers / "model-a.jsonl", [])

            with self.assertRaisesRegex(RuntimeError, "Single grading incomplete"):
                run_judge_single(
                    str(questions),
                    str(answers),
                    str(root / "judgments"),
                    "model-a",
                    ChatClient.mock(),
                    sleep_between_calls=0,
                )

    def test_pairwise_missing_answer_is_nonzero_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            questions = root / "questions.jsonl"
            answers = root / "answers"
            _write_jsonl(questions, [_question()])
            _write_jsonl(answers / "model-a.jsonl", [])
            _write_jsonl(answers / "model-b.jsonl", [])

            with self.assertRaisesRegex(RuntimeError, "Pairwise grading incomplete"):
                run_judge_pairwise(
                    str(questions),
                    str(answers),
                    str(root / "judgments"),
                    "model-a",
                    "model-b",
                    ChatClient.mock(),
                    sleep_between_calls=0,
                )

    def test_reference_missing_answer_is_nonzero_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            questions = root / "questions.jsonl"
            answers = root / "answers"
            _write_jsonl(questions, [_question(["one", "two"])])
            _write_jsonl(answers / "model-a.jsonl", [])

            with self.assertRaisesRegex(
                RuntimeError, "Reference-guided single grading incomplete"
            ):
                run_judge_reference_single(
                    str(questions),
                    str(answers),
                    str(root / "judgments"),
                    "model-a",
                    ChatClient.mock(),
                    sleep_between_calls=0,
                )

    def test_historical_reference_selection_matches_paper_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            questions = root / "questions.jsonl"
            answers = root / "answers"
            _write_jsonl(questions, [_question(["first-turn reference", ""])])
            _write_jsonl(
                answers / "model-a.jsonl",
                [{
                    "question_id": 81,
                    "model_id": "model-a",
                    "choices": [{"index": 0, "turns": ["a1", "a2"]}],
                }],
            )

            run_judge_reference_single(
                str(questions),
                str(answers),
                str(root / "judgments"),
                "model-a",
                ChatClient.mock(),
                sleep_between_calls=0,
                reference_selection="historical-declared",
            )

            output = root / "judgments" / "single_grade_ref" / "model-a.jsonl"
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual([row["question_id"] for row in rows], [81])


if __name__ == "__main__":
    unittest.main()
