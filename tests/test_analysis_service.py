import unittest
from unittest.mock import patch

from utils.analysis_service import run_business_analysis


class AnalysisServiceTests(unittest.TestCase):
    @patch("utils.analysis_service.run_local_analysis")
    @patch("utils.analysis_service.run_nexus_workflow")
    def test_provider_failure_returns_a_labeled_local_answer(
        self, run_provider, run_local
    ):
        run_provider.side_effect = RuntimeError("503 temporarily unavailable")
        run_local.return_value = {
            "final_recommendation": "Local recommendation",
            "error": None,
        }

        result = run_business_analysis("check inventory", use_provider=True)

        self.assertEqual(result["mode"], "Local fallback analytics")
        self.assertEqual(result["final_recommendation"], "Local recommendation")
        self.assertIn("temporarily unavailable", result["fallback_notice"])
        run_local.assert_called_once_with("check inventory")

    @patch("utils.analysis_service.run_local_analysis")
    def test_local_mode_does_not_call_provider(self, run_local):
        run_local.return_value = {"final_recommendation": "Local"}

        result = run_business_analysis("check inventory", use_provider=False)

        self.assertEqual(result["mode"], "Local demo analytics")
        self.assertIn("GROQ_API_KEY is not configured", result["fallback_notice"])
        run_local.assert_called_once_with("check inventory")


if __name__ == "__main__":
    unittest.main()