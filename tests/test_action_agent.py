import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agents.action_agent import (
    _clean_business_answer,
    _direct_answer_only,
    run_action_agent,
)


class ActionAgentPromptTests(unittest.TestCase):
    def test_direct_answer_filter_removes_repeated_sections(self):
        response = (
            "## Action Agent — Final Recommendation\n\n"
            "### Direct answer\nTop result: Customer A.\n\n"
            "### Relevant evidence\nRepeated facts.\n\n"
            "### Next step\nUnrequested advice."
        )

        result = _direct_answer_only(response)

        self.assertIn("Customer A", result)
        self.assertNotIn("Relevant evidence", result)
        self.assertNotIn("Next step", result)
        self.assertNotIn("Direct answer", result)
        self.assertNotIn("Action Agent", result)

    def test_business_answer_removes_agent_and_section_labels(self):
        response = (
            "## 🚀 Action Agent — Final Recommendation\n\n"
            "### Direct answer\nEast had the lowest recorded revenue.\n\n"
            "### Relevant evidence\nInternal evidence."
        )

        result = _clean_business_answer(_direct_answer_only(response))

        self.assertEqual(result, "East had the lowest recorded revenue.")

    def test_business_answer_drops_unsolicited_evidence_and_follow_up(self):
        response = (
            "East had the lowest recorded revenue.\n\n"
            "### Relevant evidence\nRepeated table values.\n\n"
            "### Next step\nCompare regions with a broader period."
        )

        self.assertEqual(
            _clean_business_answer(response),
            "East had the lowest recorded revenue.",
        )

    @patch("agents.action_agent.invoke_with_fallback")
    def test_omits_automation_payload_when_flow_is_disabled(self, invoke):
        invoke.return_value = SimpleNamespace(content="Direct answer")

        run_action_agent("What changed?", "facts", "context", "review")

        prompt = invoke.call_args.args[0][1].content
        self.assertIn("Do not include JSON", prompt)
        self.assertIn("Do not add section headings", prompt)
        self.assertNotIn("Because Power Automate is enabled", prompt)

    @patch("agents.action_agent.invoke_with_fallback")
    def test_requests_automation_payload_only_when_enabled(self, invoke):
        invoke.return_value = SimpleNamespace(content="Direct answer")

        run_action_agent(
            "What changed?", "facts", "context", "review", trigger_flow=True
        )

        prompt = invoke.call_args.args[0][1].content
        self.assertIn("Because Power Automate is enabled", prompt)
        self.assertIn('"confidence"', prompt)
        self.assertNotIn("Do not include JSON", prompt)


if __name__ == "__main__":
    unittest.main()