import tempfile
import unittest
from pathlib import Path

from scripts.tools.release_manifest import is_published_data_file


class ReleaseManifestAllowlistTest(unittest.TestCase):
    def _allowed(self, relative: str) -> bool:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "data"
            path = data_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("test", encoding="utf-8")
            return is_published_data_file(
                path, data_root, data_root / "MANIFEST.sha256"
            )

    def test_unscored_corrected_drafts_are_not_included(self):
        self.assertFalse(self._allowed("corrected/README.md"))
        self.assertFalse(self._allowed("corrected/ko/questions_v2.jsonl"))

    def test_answers_require_exact_depth_and_jsonl_extension(self):
        self.assertTrue(self._allowed("en/answers/model.jsonl"))
        self.assertFalse(self._allowed("en/answers/model.jsonl.bak"))
        self.assertFalse(self._allowed("en/answers/archive/model.jsonl"))

    def test_judgments_require_canonical_protocol_and_jsonl(self):
        canonical = "ko/judgments/qwen/judge_7B/pairwise/model-a_vs_model-b.jsonl"
        self.assertTrue(self._allowed(canonical))
        self.assertFalse(self._allowed(canonical + ".bak"))
        self.assertFalse(
            self._allowed("ko/judgments/qwen/judge_7B/logs/run.jsonl")
        )

    def test_translation_review_accepts_only_csv_at_expected_depth(self):
        self.assertTrue(self._allowed("translation_review/items.csv"))
        self.assertFalse(self._allowed("translation_review/items.json"))
        self.assertFalse(self._allowed("translation_review/archive/items.csv"))


if __name__ == "__main__":
    unittest.main()
