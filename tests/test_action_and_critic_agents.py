import os
import unittest
from unittest.mock import patch

from agents.action_agent import run_action_agent
from agents.critic_agent import run_critic_agent
from utils.tools import trigger_power_automate


class ActionAndCriticAgentTests(unittest.TestCase):
    def test_inventory_action_uses_reorder_decision_and_caveat(self):
        recommendation, status = run_action_agent(
            question="Which products are below reorder threshold, and what should we do?",
            analyst_findings="Analyst inventory findings",
            research_insights="Research context",
            critic_review="Critic review",
        )

        self.assertEqual(status, "")
        self.assertIn("REORDER · medium urgency", recommendation)
        self.assertIn("SecureShield Antivirus", recommendation)
        self.assertIn("DevOps Pipeline Kit", recommendation)
        self.assertIn("does not include current demand", recommendation)

    @patch("agents.action_agent.trigger_power_automate")
    def test_inventory_action_sends_the_recommendation_payload(self, trigger):
        trigger.return_value = "✅ Power Automate flow triggered successfully (HTTP 202)."

        recommendation, status = run_action_agent(
            question="Which products are at risk of stockout?",
            analyst_findings="Analyst inventory findings",
            research_insights="Research context",
            critic_review="Critic review",
            trigger_flow=True,
        )

        payload = trigger.call_args.args[0]
        self.assertEqual(payload["decision"], "REORDER")
        self.assertEqual(payload["confidence"], 85)
        self.assertEqual(payload["urgency"], "MEDIUM")
        self.assertIn("SecureShield Antivirus", payload["top_action"])
        self.assertIn("HTTP 202", status)
        self.assertIn("REORDER · medium urgency", recommendation)

    @patch("agents.critic_agent.invoke_with_fallback")
    def test_inventory_critic_caps_confidence_and_names_data_gaps(self, invoke):
        invoke.return_value = type(
            "Response",
            (),
            {"content": "Confidence: 100%. The sample table is internally consistent."},
        )()

        review = run_critic_agent(
            "Which products are at risk of stockout?",
            "Inventory findings",
            "Research context",
        )

        self.assertIn("Confidence: 90%", review)
        self.assertNotIn("100%", review)
        self.assertIn("current demand", review)
        self.assertIn("supplier lead times", review)
        self.assertIn("purchase-order status", review)

    @patch("agents.critic_agent.invoke_with_fallback")
    def test_general_critic_includes_historical_data_limitation(self, invoke):
        invoke.return_value = type("Response", (), {"content": "The ranking is consistent."})()

        review = run_critic_agent(
            "Who are the top customers by revenue?",
            "Customer results",
            "Research context",
        )

        self.assertIn("Confidence: 85%", review)
        self.assertIn("synthetic 2025 sample is historical", review)

    @patch("agents.critic_agent.invoke_with_fallback")
    def test_inventory_critic_adds_all_operational_data_gaps(self, invoke):
        invoke.return_value = type(
            "Response",
            (),
            {"content": "Confidence: 82%. This is based on historical data."},
        )()

        review = run_critic_agent(
            "Which products are at risk of stockout?",
            "Inventory findings",
            "Research context",
        )

        self.assertIn("Confidence: 82%", review)
        self.assertIn("current demand", review)
        self.assertIn("supplier lead times", review)
        self.assertIn("purchase-order status", review)

    @patch("agents.critic_agent.invoke_with_fallback")
    def test_critic_caps_confident_wording_without_a_confidence_label(self, invoke):
        invoke.return_value = type(
            "Response",
            (),
            {"content": "I am 100% confident in the ranking."},
        )()

        review = run_critic_agent(
            "Who are the top customers by revenue?",
            "Customer results",
            "Research context",
        )

        self.assertIn("90% confident", review)
        self.assertNotIn("100%", review)

    def test_missing_webhook_reports_that_no_request_was_sent(self):
        with patch.dict(os.environ, {"POWER_AUTOMATE_WEBHOOK_URL": ""}):
            status = trigger_power_automate({"decision": "REORDER"})

        self.assertIn("no request was sent", status)
        self.assertNotIn("Would have sent", status)


if __name__ == "__main__":
    unittest.main()
