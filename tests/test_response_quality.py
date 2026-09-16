import unittest

from agent.nodes import _parse_generation_flexible
from legal.citations import validate_citations


class ResponseQualityRegressionTests(unittest.TestCase):
    def test_parser_does_not_invent_citations(self):
        generation = _parse_generation_flexible(
            "Người sử dụng lao động phải thực hiện nghĩa vụ này.",
            [{"strip_id": "DOC_1", "text": "Một đoạn bằng chứng."}],
        )

        self.assertEqual(generation["claims"], [])

    def test_uncited_non_abstaining_answer_fails_validation(self):
        report = validate_citations(
            {"answer": "Có nghĩa vụ phải thực hiện.", "claims": [], "abstain": False},
            {"DOC_1": {"text": "Bằng chứng", "status": "effective"}},
        )

        self.assertFalse(report["ok"])
        self.assertEqual(report["citation_coverage"], 0.0)


if __name__ == "__main__":
    unittest.main()
