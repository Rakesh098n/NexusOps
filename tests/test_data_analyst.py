import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agents.data_analyst import _split_select_statements, run_data_analyst


class DataAnalystSqlTests(unittest.TestCase):
    def test_splits_two_selects_returned_on_one_line(self):
        sql = (
            "SELECT customer_id FROM customers LIMIT 10; "
            "SELECT customer_id FROM customers;"
        )

        self.assertEqual(
            _split_select_statements(sql),
            [
                "SELECT customer_id FROM customers LIMIT 10;",
                "SELECT customer_id FROM customers;",
            ],
        )

    def test_does_not_split_semicolons_inside_sql_strings(self):
        sql = "SELECT 'a; b' AS label; SELECT customer_id FROM customers;"

        self.assertEqual(
            _split_select_statements(sql),
            ["SELECT 'a; b' AS label;", "SELECT customer_id FROM customers;"],
        )

    def test_rejects_mixed_read_and_write_statements(self):
        sql = "SELECT product_id FROM products; DELETE FROM inventory;"

        self.assertEqual(_split_select_statements(sql), [])

    def test_unsafe_generated_sql_produces_a_clear_error_without_execution(self):
        with patch("agents.data_analyst.invoke_with_fallback") as invoke:
            invoke.return_value = SimpleNamespace(
                content="DELETE FROM inventory;"
            )

            result = run_data_analyst("Clear the inventory table", "schema")

        self.assertIn("Only read-only SELECT queries are allowed", result)
        self.assertIn("was not executed", result)
        self.assertEqual(invoke.call_count, 1)

    @patch("agents.data_analyst.run_sql_query", return_value="top customers table")
    @patch("agents.data_analyst.invoke_with_fallback")
    def test_executes_only_one_statement_from_combined_model_output(
        self, invoke, run_sql
    ):
        invoke.side_effect = [
            SimpleNamespace(
                content=(
                    "SELECT customer_id FROM customers LIMIT 10; "
                    "SELECT customer_id FROM customers;"
                )
            ),
            SimpleNamespace(content="Top customers by revenue are listed above."),
        ]

        result = run_data_analyst("Who are the top customers?", "customers schema")

        run_sql.assert_called_once_with(
            "SELECT customer_id FROM customers LIMIT 10;"
        )
        self.assertIn("top customers table", result)
        self.assertNotIn("SQL Error", result)

    @patch("agents.data_analyst.run_sql_query", return_value="| East | USD 10 |")
    @patch("agents.data_analyst.invoke_with_fallback")
    def test_findings_show_results_without_displaying_generated_sql(
        self, invoke, run_sql
    ):
        invoke.side_effect = [
            SimpleNamespace(
                content="SELECT name, revenue FROM regions ORDER BY revenue LIMIT 1;"
            ),
            SimpleNamespace(content="East has the lowest recorded revenue."),
        ]

        result = run_data_analyst("Which region has lowest revenue?", "schema")

        self.assertIn("East", result)
        self.assertIn("Observed data", result)
        self.assertNotIn("**Query:**", result)
        self.assertNotIn("SELECT name", result)
        run_sql.assert_called_once()


if __name__ == "__main__":
    unittest.main()