import unittest

from mtbench_repro.prompts import (
    build_multiturn_pairwise_prompt,
    build_multiturn_pairwise_reference_prompt,
    build_multiturn_single_prompt,
    build_single_prompt,
)


class PromptProtocolTest(unittest.TestCase):
    def test_single_turn_uses_upstream_role_boundary(self):
        messages = build_single_prompt("question", "answer", lang="en")

        self.assertEqual(messages[0]["content"], "You are a helpful assistant.")
        self.assertTrue(messages[1]["content"].startswith("[Instruction]\n"))
        self.assertIn("[Question]\nquestion", messages[1]["content"])

    def test_multiturn_prompts_explicitly_focus_on_second_question(self):
        single = build_multiturn_single_prompt(
            ["question 1", "question 2"], ["answer 1", "answer 2"], lang="en"
        )
        pairwise = build_multiturn_pairwise_prompt(
            ["question 1", "question 2"],
            ["answer a1", "answer a2"],
            ["answer b1", "answer b2"],
            lang="en",
        )

        self.assertIn("second user question", single[0]["content"])
        self.assertIn("second user question", pairwise[0]["content"])

    def test_reference_multiturn_omits_an_empty_legacy_slot(self):
        messages = build_multiturn_pairwise_reference_prompt(
            ["question 1", "question 2"],
            ["answer a1", "answer a2"],
            ["answer b1", "answer b2"],
            ["reference 1", ""],
            lang="en",
        )

        self.assertIn("second user question", messages[0]["content"])
        self.assertEqual(messages[1]["content"].count("### Reference answer:"), 1)

    def test_korean_multiturn_prompts_preserve_second_question_focus(self):
        single = build_multiturn_single_prompt(
            ["질문 1", "질문 2"], ["답변 1", "답변 2"], lang="ko"
        )
        pairwise = build_multiturn_pairwise_prompt(
            ["질문 1", "질문 2"],
            ["A 답변 1", "A 답변 2"],
            ["B 답변 1", "B 답변 2"],
            lang="ko",
        )

        self.assertIn("두 번째 사용자 질문", single[0]["content"])
        self.assertIn("두 번째 사용자 질문", pairwise[0]["content"])


if __name__ == "__main__":
    unittest.main()
