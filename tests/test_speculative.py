"""
Standard library unit tests for Kora AI Speculative Decoding Engine.
"""

import unittest
from core.models.speculative import SpeculativeDecoder, SpeculativeResult


class TestSpeculativeDecoder(unittest.TestCase):
    def test_verify_tokens_all_accepted(self):
        decoder = SpeculativeDecoder(lookahead_k=4)
        draft = ["import", " ", "os", "\n"]
        validator = lambda tokens: [True] * len(tokens)

        accepted, _ = decoder.verify_tokens(draft, validator)
        self.assertEqual(accepted, draft)

    def test_verify_tokens_partial_rejection(self):
        decoder = SpeculativeDecoder(lookahead_k=4)
        draft = ["class", " ", "FastEngine", ":"]
        # Accept first 2 tokens, reject 3rd
        validator = lambda tokens: [True, True, False, True][:len(tokens)]

        accepted, _ = decoder.verify_tokens(draft, validator)
        self.assertEqual(accepted, ["class", " "])

    def test_speculative_run_speedup_calculation(self):
        decoder = SpeculativeDecoder(lookahead_k=4)

        result = decoder.run(
            prompt="def solve():",
            max_iterations=1,
            draft_generator_fn=lambda p, k: ["return", " ", "True"],
            target_validator_fn=lambda tokens: [True, True, True],
        )

        self.assertIsInstance(result, SpeculativeResult)
        self.assertEqual(result.draft_tokens_proposed, 3)
        self.assertEqual(result.draft_tokens_accepted, 3)
        self.assertEqual(result.acceptance_rate, 1.0)
        self.assertGreater(result.effective_speedup_ratio, 2.0)
        self.assertEqual(result.generated_text, "return True")


if __name__ == "__main__":
    unittest.main()
