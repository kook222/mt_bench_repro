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
        cls.all_judges = PAPER.active_judges(cls.data_root)
        cls.baseline_judges = PAPER.baseline_judges(cls.data_root)
        cls.gemma = PAPER.gemma4_judge(cls.data_root)

    def test_baseline_judge_set(self):
        self.assertEqual(
            [judge.display for judge in self.baseline_judges],
            ["Qwen-7B", "Qwen-14B", "Qwen-32B", "EXAONE-32B", "GPT-4o-mini"],
        )
        self.assertEqual(
            [judge.display for judge in self.all_judges],
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

    def test_pairwise_table_matches_paper_baseline(self):
        rows = PAPER.build_pairwise_table(self.data_root, self.baseline_judges)
        observed = {
            row["judge"]: (row["en_rate_pct"], row["ko_rate_pct"])
            for row in rows
        }
        self.assertEqual(observed["Qwen-7B"], (79.25, 45.07))
        self.assertEqual(observed["Qwen-14B"], (45.08, 23.25))
        self.assertEqual(observed["Qwen-32B"], (30.97, 20.43))
        self.assertEqual(observed["EXAONE-32B"], (42.17, 30.5))
        self.assertEqual(observed["GPT-4o-mini"], (33.45, 21.58))
        self.assertEqual(observed["Mean"], (46.18, 28.17))

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
        rows = PAPER.build_single_table(self.data_root, self.baseline_judges)
        qwen_7b = rows[0]
        self.assertEqual(qwen_7b["en_valid_scores"], 960)
        self.assertEqual(qwen_7b["ko_valid_scores"], 915)
        self.assertEqual(qwen_7b["en_mean"], 7.81)
        self.assertEqual(qwen_7b["ko_mean"], 6.6)
        self.assertEqual(rows[-1]["en_mean"], 7.83)
        self.assertEqual(rows[-1]["ko_mean"], 6.66)
        self.assertEqual(rows[-1]["delta_ko_minus_en"], -1.17)

    def test_reference_table_matches_paired_baseline(self):
        rows = PAPER.build_reference_table(self.data_root, self.baseline_judges)
        observed = {row["judge"]: row for row in rows}
        self.assertEqual(observed["Qwen-7B"]["ko_paired"], 114)
        self.assertEqual(observed["Qwen-7B"]["ko_delta"], -1.28)
        self.assertEqual(observed["GPT-4o-mini"]["en_delta"], -2.25)
        self.assertEqual(observed["Mean"]["en_reference_mean"], 5.99)
        self.assertEqual(observed["Mean"]["ko_reference_mean"], 5.33)

        self.assertEqual(observed["Mean"]["en_standard_mean"], 7.61)
        self.assertEqual(observed["Mean"]["en_delta"], -1.62)
        self.assertEqual(observed["Mean"]["ko_standard_mean"], 6.67)
        self.assertEqual(observed["Mean"]["ko_delta"], -1.33)

    def test_failures_preserve_error_type(self):
        rows = PAPER.build_failure_table(self.data_root, self.baseline_judges)
        keyed = {
            (row["language"], row["judge"], row["protocol"]): row
            for row in rows
        }
        qwen_reference = keyed[("ko", "Qwen-7B", "single_grade_ref")]
        self.assertEqual(qwen_reference["format_parse_failures"], 58)
        gpt_pairwise = keyed[("en", "GPT-4o-mini", "pairwise")]
        self.assertEqual(gpt_pairwise["empty_or_api_failures"], 13)
        self.assertEqual(gpt_pairwise["format_parse_failures"], 0)

    def test_gemma4_is_reported_separately_by_v3_protocol(self):
        rows = PAPER.build_gemma4_robustness_table(self.data_root, self.gemma)
        self.assertEqual(len(rows), 6)
        keyed = {(row["language"], row["evaluation"]): row for row in rows}

        en_single = keyed[("en", "single_grade")]
        self.assertEqual(en_single["prompt_protocol"], "single-grade-fastchat-role-v3")
        self.assertEqual(en_single["metric_value"], 7.51)
        self.assertEqual(en_single["metric_denominator"], 957)
        self.assertEqual(en_single["format_parse_failures"], 3)

        ko_single = keyed[("ko", "single_grade")]
        self.assertEqual(ko_single["metric_value"], 5.56)
        self.assertEqual(ko_single["metric_denominator"], 956)
        self.assertEqual(ko_single["format_parse_failures"], 4)

        en_pairwise = keyed[("en", "pairwise")]
        self.assertEqual(en_pairwise["metric_numerator"], 234)
        self.assertEqual(en_pairwise["metric_denominator"], 1180)
        self.assertEqual(en_pairwise["metric_value"], 19.83)
        self.assertEqual(en_pairwise["position_first_count"], 172)
        self.assertEqual(en_pairwise["position_first_pct"], 73.5)
        self.assertEqual(en_pairwise["position_second_count"], 41)
        self.assertEqual(en_pairwise["position_second_pct"], 17.52)
        self.assertEqual(en_pairwise["other_inconsistent_count"], 21)
        self.assertEqual(en_pairwise["other_inconsistent_pct"], 8.97)
        self.assertEqual(en_pairwise["format_parse_failures"], 20)

        ko_pairwise = keyed[("ko", "pairwise")]
        self.assertEqual(ko_pairwise["metric_numerator"], 176)
        self.assertEqual(ko_pairwise["metric_denominator"], 1197)
        self.assertEqual(ko_pairwise["metric_value"], 14.7)
        self.assertEqual(ko_pairwise["position_first_count"], 108)
        self.assertEqual(ko_pairwise["position_first_pct"], 61.36)
        self.assertEqual(ko_pairwise["position_second_count"], 54)
        self.assertEqual(ko_pairwise["position_second_pct"], 30.68)
        self.assertEqual(ko_pairwise["other_inconsistent_count"], 14)
        self.assertEqual(ko_pairwise["other_inconsistent_pct"], 7.95)
        self.assertEqual(ko_pairwise["format_parse_failures"], 3)

        en_reference = keyed[("en", "single_grade_ref")]
        self.assertEqual(en_reference["standard_mean"], 5.23)
        self.assertEqual(en_reference["reference_mean"], 4.65)
        self.assertEqual(en_reference["reference_delta"], -0.59)
        self.assertEqual(en_reference["metric_denominator"], 172)

        ko_reference = keyed[("ko", "single_grade_ref")]
        self.assertEqual(ko_reference["standard_mean"], 4.45)
        self.assertEqual(ko_reference["reference_mean"], 3.95)
        self.assertEqual(ko_reference["reference_delta"], -0.5)
        self.assertEqual(ko_reference["metric_denominator"], 173)

        self.assertTrue(
            all(row["empty_or_api_failures"] == 0 for row in rows)
        )
        self.assertTrue(all(row["missing_calls"] == 0 for row in rows))
        self.assertEqual(
            {
                key: (row["expected_calls"], row["valid_calls"])
                for key, row in keyed.items()
            },
            {
                ("en", "single_grade"): (960, 957),
                ("en", "pairwise"): (2400, 2380),
                ("en", "single_grade_ref"): (174, 174),
                ("ko", "single_grade"): (960, 956),
                ("ko", "pairwise"): (2400, 2397),
                ("ko", "single_grade_ref"): (174, 174),
            },
        )

    def test_primary_figure_excludes_gemma4(self):
        rows = PAPER.build_figure_rows(self.data_root, self.baseline_judges)
        self.assertEqual(len(rows), 28)
        self.assertTrue(all("gemma_4_12b" not in row for row in rows))
        self.assertTrue(all("judge_mean" in row for row in rows))

    def test_primary_figure_is_two_by_two_full_width_figure(self):
        rows = PAPER.build_figure_rows(self.data_root, self.baseline_judges)
        with tempfile.TemporaryDirectory() as directory:
            figure_dir = Path(directory)
            PAPER.render_figure(rows, self.baseline_judges, figure_dir)
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
