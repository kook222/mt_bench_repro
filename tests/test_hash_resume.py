import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from mtbench_repro.client import ChatClient
from mtbench_repro.io_utils import (
    get_processed_inputs,
    stable_fingerprint,
    upsert_jsonl,
)
from mtbench_repro.generate import (
    answer_record_is_current,
    generate_answer,
    generation_input_fingerprint,
)
from mtbench_repro.judge_pairwise import (
    pairwise_input_fingerprint,
    pairwise_record_is_current,
)
from mtbench_repro.judge_single import (
    single_input_fingerprint,
    single_record_is_current,
)
from mtbench_repro.schemas import MTBenchQuestion, ModelAnswer


class HashResumeTest(unittest.TestCase):
    def test_generation_calls_the_model_id_recorded_in_the_answer(self):
        question = MTBenchQuestion(81, "writing", ["q1", "q2"])
        client = ChatClient.mock()
        called_models = []

        def chat(_messages, model=None, **_kwargs):
            called_models.append(model)
            return "answer"

        client.chat = chat
        answer = generate_answer(question, "claimed-model", client)

        self.assertEqual(called_models, ["claimed-model", "claimed-model"])
        self.assertEqual(answer.model_id, "claimed-model")

    def test_upsert_replaces_same_question_without_duplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.jsonl"
            upsert_jsonl(path, {"question_id": 83, "input_sha256": "old"})
            upsert_jsonl(path, {"question_id": 83, "input_sha256": "new"})

            rows = [json.loads(line) for line in path.read_text().splitlines()]

        self.assertEqual(rows, [{"question_id": 83, "input_sha256": "new"}])

    def test_concurrent_upserts_do_not_lose_records(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.jsonl"

            def write_one(question_id: int) -> None:
                upsert_jsonl(
                    path,
                    {"question_id": question_id, "input_sha256": str(question_id)},
                )

            with ThreadPoolExecutor(max_workers=8) as executor:
                list(executor.map(write_one, range(32)))

            rows = [json.loads(line) for line in path.read_text().splitlines()]

        self.assertEqual(len(rows), 32)
        self.assertEqual({row["question_id"] for row in rows}, set(range(32)))

    def test_processed_inputs_returns_only_hashed_records(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.jsonl"
            path.write_text(
                '{"question_id": 1}\n'
                '{"question_id": 2, "input_sha256": "hash"}\n',
                encoding="utf-8",
            )

            self.assertEqual(get_processed_inputs(path), {2: "hash"})

    def test_fingerprint_is_key_order_independent(self):
        self.assertEqual(
            stable_fingerprint({"a": 1, "b": 2}),
            stable_fingerprint({"b": 2, "a": 1}),
        )

    def test_generation_hash_ignores_reference_only_metadata(self):
        original = MTBenchQuestion(
            question_id=136,
            category="extraction",
            turns=["same first prompt", "same second prompt"],
            reference=["old", "old"],
        )
        corrected_reference = MTBenchQuestion(
            question_id=136,
            category="extraction",
            turns=["same first prompt", "same second prompt"],
            reference=["new", "new"],
        )
        arguments = ("model", 0.7, 1024, "answer in Korean")

        self.assertEqual(
            generation_input_fingerprint(original, *arguments),
            generation_input_fingerprint(corrected_reference, *arguments),
        )

    def test_judge_hash_tracks_category_and_backend(self):
        writing = MTBenchQuestion(1, "writing", ["q1", "q2"])
        math = MTBenchQuestion(1, "math", ["q1", "q2"])
        answer_a = ModelAnswer(1, "a", [{"index": 0, "turns": ["a1", "a2"]}])
        answer_b = ModelAnswer(1, "b", [{"index": 0, "turns": ["b1", "b2"]}])
        backend_a = {"provider": "openai_compatible", "base_url": "https://a.test/v1"}
        backend_b = {"provider": "openai_compatible", "base_url": "https://b.test/v1"}

        self.assertNotEqual(
            single_input_fingerprint(writing, answer_a, "judge", "en", backend_a),
            single_input_fingerprint(math, answer_a, "judge", "en", backend_a),
        )
        self.assertNotEqual(
            pairwise_input_fingerprint(
                writing, answer_a, answer_b, "judge", "en", backend_a
            ),
            pairwise_input_fingerprint(
                writing, answer_a, answer_b, "judge", "en", backend_b
            ),
        )

    def test_resume_rejects_truncated_record_even_with_matching_hash(self):
        question = MTBenchQuestion(81, "writing", ["q1", "q2"])
        answer = ModelAnswer(
            81,
            "model-a",
            [{"index": 0, "turns": ["a1", "a2"]}],
        )
        generation_hash = generation_input_fingerprint(
            question, "model-a", 0.7, 1024, None
        )
        truncated_answer = {
            "question_id": 81,
            "model_id": "model-a",
            "choices": [{"index": 0, "turns": ["a1"]}],
            "input_sha256": generation_hash,
        }
        self.assertFalse(
            answer_record_is_current(
                truncated_answer, 81, "model-a", generation_hash
            )
        )

        single_hash = single_input_fingerprint(
            question, answer, "judge", "en"
        )
        truncated_single = {
            "question_id": 81,
            "model_id": "model-a",
            "judge_id": "judge",
            "category": "writing",
            "score_turn1": 5.0,
            "score_turn2": 5.0,
            "judgment_turn1": "[[5]]",
            "judgment_turn2": "",
            "input_sha256": single_hash,
        }
        self.assertFalse(
            single_record_is_current(
                truncated_single, question, "model-a", "judge", single_hash
            )
        )

        answer_b = ModelAnswer(
            81,
            "model-b",
            [{"index": 0, "turns": ["b1", "b2"]}],
        )
        pairwise_hash = pairwise_input_fingerprint(
            question, answer, answer_b, "judge", "en"
        )
        malformed_pairwise = {
            "question_id": 81,
            "model_a": "model-a",
            "model_b": "model-b",
            "judge_id": "judge",
            "category": "writing",
            "turn": 2,
            "winner": "not-a-verdict",
            "winner_ab": "A",
            "winner_ba": "B",
            "judgment_ab": "[[A]]",
            "judgment_ba": "[[B]]",
            "input_sha256": pairwise_hash,
        }
        self.assertFalse(
            pairwise_record_is_current(
                malformed_pairwise,
                question,
                "model-a",
                "model-b",
                "judge",
                pairwise_hash,
            )
        )

        inconsistent_winner = dict(malformed_pairwise)
        inconsistent_winner.update(
            {
                "winner": "model-a",
                "winner_ab": "A",
                "winner_ba": "A",
            }
        )
        self.assertFalse(
            pairwise_record_is_current(
                inconsistent_winner,
                question,
                "model-a",
                "model-b",
                "judge",
                pairwise_hash,
            )
        )


if __name__ == "__main__":
    unittest.main()
