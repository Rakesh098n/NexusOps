import unittest

from utils.local_analytics import (
    build_inventory_scenario,
    get_inventory_snapshot,
    run_local_analysis,
)


class LocalAnalyticsTests(unittest.TestCase):
    def test_inventory_scenario_calculates_target_and_order_gap(self):
        scenario = build_inventory_scenario(
            get_inventory_snapshot(include_demand=True),
            lead_time_days=14,
            safety_stock_days=7,
        )

        secure_shield = next(
            row for row in scenario["rows"]
            if row["product"] == "SecureShield Antivirus"
        )
        self.assertEqual(scenario["lead_time_days"], 14)
        self.assertEqual(scenario["safety_stock_days"], 7)
        self.assertEqual(secure_shield["target_stock"], 59)
        self.assertEqual(secure_shield["suggested_order_quantity"], 47)
        self.assertEqual(secure_shield["decision"], "REORDER")
        self.assertTrue(
            all(row["suggested_order_quantity"] >= 0 for row in scenario["rows"])
        )

    def test_inventory_snapshot_does_not_expose_demand_by_default(self):
        self.assertNotIn("avg_daily_demand", get_inventory_snapshot().columns)

    def test_stockout_questions_route_to_inventory(self):
        result = run_local_analysis("Which products are at risk of stockout?")

        self.assertEqual(result["focus"], "Inventory and stock coverage")
        self.assertIn("SecureShield Antivirus", result["analyst_findings"])
        self.assertIn("DevOps Pipeline Kit", result["analyst_findings"])
        self.assertIn("REORDER · medium urgency", result["final_recommendation"])
        self.assertIn("flags 3 of 8 products", result["final_recommendation"])
        self.assertIn("medium urgency", result["final_recommendation"])
        self.assertIn("if they remain below threshold", result["final_recommendation"])
        self.assertIn("supplier lead times", result["final_recommendation"])
        self.assertNotIn("Direct answer", result["final_recommendation"])
        self.assertNotIn("Relevant evidence", result["final_recommendation"])
        self.assertNotIn("Next step", result["final_recommendation"])
        self.assertIn("Confidence: 85%", result["critic_review"])
        self.assertIn("current demand", result["critic_review"])

    def test_top_customer_count_matches_question(self):
        result = run_local_analysis("Who are our top 5 customers by revenue in 2025?")
        table = result["analyst_findings"].split("\n\n", 1)[1]
        table_rows = [line for line in table.splitlines() if line.startswith("|")]

        self.assertEqual(result["focus"], "Top 5 customers by recorded revenue")
        self.assertEqual(len(table_rows), 7)

    def test_top_customers_question_returns_ranked_sample_revenue(self):
        result = run_local_analysis("Who are the top customers by revenue?")

        self.assertEqual(result["focus"], "Top 10 customers by recorded revenue")
        self.assertIn("Customer_084", result["final_recommendation"])
        self.assertIn("USD ", result["final_recommendation"])
        self.assertIn("10. ", result["final_recommendation"])
        self.assertNotIn("Use this ranking", result["final_recommendation"])

    def test_lowest_region_question_identifies_lowest_revenue(self):
        result = run_local_analysis("Which region has the lowest sales performance?")

        self.assertEqual(result["focus"], "Recorded revenue by region")
        self.assertIn("East recorded the lowest", result["final_recommendation"])
        self.assertIn("USD ", result["final_recommendation"])
        self.assertNotIn("Compare regional results", result["final_recommendation"])

    def test_named_category_question_filters_products(self):
        result = run_local_analysis(
            "Should we increase marketing budget for Analytics products?"
        )

        self.assertEqual(result["focus"], "Revenue from Analytics products")
        self.assertIn("AnalyticsPulse", result["analyst_findings"])
        self.assertNotIn("Nexus CRM Suite", result["analyst_findings"])

    def test_q4_category_question_uses_requested_period(self):
        result = run_local_analysis(
            "Compare revenue across product categories for Q4 2025."
        )

        self.assertEqual(
            result["focus"], "Revenue by product category for Q4 2025"
        )
        self.assertNotIn("e+", result["analyst_findings"])
        self.assertNotIn("marketing budget", result["final_recommendation"])

    def test_general_product_question_returns_product_rows(self):
        result = run_local_analysis("Which products had the highest revenue?")

        self.assertEqual(result["focus"], "Revenue by product")
        self.assertIn("Nexus CRM Suite", result["analyst_findings"])
        self.assertIn("units sold", result["final_recommendation"])
        self.assertNotIn("marketing budget", result["final_recommendation"])

    def test_financial_summary_uses_unambiguous_currency(self):
        result = run_local_analysis("How did monthly revenue trend?")

        self.assertIn("USD ", result["final_recommendation"])
        self.assertNotIn("e+", result["analyst_findings"])


if __name__ == "__main__":
    unittest.main()