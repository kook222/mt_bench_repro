import csv
import importlib.util
import re
import struct
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "analysis" / "build_paper_artifacts.py"
SPEC = importlib.util.spec_from_file_location("build_paper_artifacts", SCRIPT)
PAPER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PAPER
assert SPEC.loader is not None
SPEC.loader.exec_module(PAPER)


class PaperArtifactTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data_root = Path(__file__).parents[1] / "data"
        cls.judges = PAPER.active_judges(cls.data_root)

    def test_judge_set(self):
        self.assertEqual(
            [judge.display for judge in self.judges],
            [
                "Qwen-7B",
                "Qwen-14B",
                "Qwen-32B",
                "EXAONE-32B",
                "GPT-4o-mini",
                "Gemma-4-12B",
            ],
        )

    def test_translation_review_counts(self):
        rows = PAPER.build_translation_review(self.data_root)
        self.assertEqual(sum(row["manual_review_candidates"] for row in rows), 34)
        self.assertEqual(sum(row["modified_items"] for row in rows), 3)
        with (self.data_root / "translation_review" / "items.csv").open(
            encoding="utf-8", newline=""
        ) as stream:
            items = list(csv.DictReader(stream))
        self.assertEqual(
            {row["question_id"] for row in items if row["modified"] == "True"},
            {"83", "90", "136"},
        )

    def test_pairwise_table_matches_paper(self):
        rows = PAPER.build_pairwise_table(self.data_root, self.judges)
        observed = {
            row["judge"]: (row["en_rate_pct"], row["ko_rate_pct"])
            for row in rows
        }
        self.assertEqual(observed["Qwen-7B"], (79.25, 45.07))
        self.assertEqual(observed["Qwen-14B"], (45.08, 23.25))
        self.assertEqual(observed["Qwen-32B"], (30.97, 20.43))
        self.assertEqual(observed["EXAONE-32B"], (42.17, 30.5))
        self.assertEqual(observed["GPT-4o-mini"], (33.45, 21.58))
        self.assertEqual(observed["Gemma-4-12B"], (19.83, 14.7))
        self.assertEqual(observed["Mean"], (41.79, 25.92))

        for row in rows:
            if row["judge"] == "Mean":
                continue
            self.assertEqual(
                row["ko_same_first"]
                + row["ko_same_second"]
                + row["ko_other_inconsistent"],
                row["ko_inconsistent"],
            )

    def test_single_table_uses_all_valid_outputs(self):
        rows = PAPER.build_single_table(self.data_root, self.judges)
        qwen_7b = rows[0]
        self.assertEqual(qwen_7b["en_valid_scores"], 960)
        self.assertEqual(qwen_7b["ko_valid_scores"], 915)
        self.assertEqual(qwen_7b["en_mean"], 7.81)
        self.assertEqual(qwen_7b["ko_mean"], 6.6)
        gemma = rows[-2]
        self.assertEqual(gemma["en_mean"], 7.51)
        self.assertEqual(gemma["en_valid_scores"], 957)
        self.assertEqual(gemma["ko_mean"], 5.56)
        self.assertEqual(gemma["ko_valid_scores"], 956)
        self.assertEqual(gemma["delta_ko_minus_en"], -1.95)
        self.assertEqual(rows[-1]["en_mean"], 7.78)
        self.assertEqual(rows[-1]["ko_mean"], 6.47)
        self.assertEqual(rows[-1]["delta_ko_minus_en"], -1.3)

    def test_reference_table_matches_paired_outputs(self):
        rows = PAPER.build_reference_table(self.data_root, self.judges)
        observed = {row["judge"]: row for row in rows}
        self.assertEqual(observed["Qwen-7B"]["ko_paired"], 114)
        self.assertEqual(observed["Qwen-7B"]["ko_delta"], -1.28)
        self.assertEqual(observed["GPT-4o-mini"]["en_delta"], -2.25)
        self.assertEqual(observed["Gemma-4-12B"]["en_standard_mean"], 5.23)
        self.assertEqual(observed["Gemma-4-12B"]["en_reference_mean"], 4.65)
        self.assertEqual(observed["Gemma-4-12B"]["en_delta"], -0.59)
        self.assertEqual(observed["Gemma-4-12B"]["en_paired"], 172)
        self.assertEqual(observed["Gemma-4-12B"]["ko_standard_mean"], 4.45)
        self.assertEqual(observed["Gemma-4-12B"]["ko_reference_mean"], 3.95)
        self.assertEqual(observed["Gemma-4-12B"]["ko_delta"], -0.5)
        self.assertEqual(observed["Gemma-4-12B"]["ko_paired"], 173)
        self.assertEqual(observed["Mean"]["en_standard_mean"], 7.21)
        self.assertEqual(observed["Mean"]["en_reference_mean"], 5.76)
        self.assertEqual(observed["Mean"]["en_delta"], -1.45)
        self.assertEqual(observed["Mean"]["ko_standard_mean"], 6.3)
        self.assertEqual(observed["Mean"]["ko_reference_mean"], 5.1)
        self.assertEqual(observed["Mean"]["ko_delta"], -1.19)

    def test_failures_preserve_error_type(self):
        rows = PAPER.build_failure_table(self.data_root, self.judges)
        keyed = {
            (row["language"], row["judge"], row["protocol"]): row
            for row in rows
        }
        qwen_reference = keyed[("ko", "Qwen-7B", "single_grade_ref")]
        self.assertEqual(qwen_reference["format_parse_failures"], 58)
        gpt_pairwise = keyed[("en", "GPT-4o-mini", "pairwise")]
        self.assertEqual(gpt_pairwise["empty_or_api_failures"], 13)
        self.assertEqual(gpt_pairwise["format_parse_failures"], 0)
        gemma_expected = {
            ("en", "single_grade"): (960, 957, 3),
            ("en", "pairwise"): (2400, 2380, 20),
            ("en", "single_grade_ref"): (174, 174, 0),
            ("ko", "single_grade"): (960, 956, 4),
            ("ko", "pairwise"): (2400, 2397, 3),
            ("ko", "single_grade_ref"): (174, 174, 0),
        }
        for (language, protocol), expected in gemma_expected.items():
            row = keyed[(language, "Gemma-4-12B", protocol)]
            self.assertEqual(
                (
                    row["expected_calls"],
                    row["valid_calls"],
                    row["format_parse_failures"],
                ),
                expected,
            )
            self.assertEqual(row["empty_or_api_failures"], 0)
            self.assertEqual(row["missing_calls"], 0)

    def test_primary_figure_includes_six_judges(self):
        rows = PAPER.build_figure_rows(self.data_root, self.judges)
        self.assertEqual(len(rows), 28)
        self.assertTrue(all("gemma_4_12b" in row for row in rows))
        self.assertTrue(all("judge_mean" in row for row in rows))

    def test_primary_figure_is_two_by_two_full_width_figure(self):
        rows = PAPER.build_figure_rows(self.data_root, self.judges)
        with tempfile.TemporaryDirectory() as directory:
            figure_dir = Path(directory)
            PAPER.render_figure(rows, self.judges, figure_dir)
            self.assertEqual(
                {path.name for path in figure_dir.iterdir() if path.is_file()},
                {"figure3_single_scores.png", "figure3_single_scores.pdf"},
            )
            png = (figure_dir / "figure3_single_scores.png").read_bytes()
            self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
            png_width, png_height = struct.unpack(">II", png[16:24])
            self.assertAlmostEqual(png_width * 25.4 / 320, 145.0, delta=0.1)
            self.assertAlmostEqual(png_height * 25.4 / 320, 94.0, delta=0.1)
            pdf = (figure_dir / "figure3_single_scores.pdf").read_bytes()
            media_box = re.search(
                rb"/MediaBox \[ 0 0 ([0-9.]+) ([0-9.]+) \]", pdf
            )
            self.assertIsNotNone(media_box)
            assert media_box is not None
            pdf_width_mm = float(media_box.group(1)) * 25.4 / 72
            pdf_height_mm = float(media_box.group(2)) * 25.4 / 72
            self.assertAlmostEqual(pdf_width_mm, 145.0, places=1)
            self.assertAlmostEqual(pdf_height_mm, 94.0, places=1)
            self.assertIn(b"/Count 1", pdf)


if __name__ == "__main__":
    unittest.main()
