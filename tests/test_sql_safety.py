import unittest

from utils.tools import run_sql_query


class SqlSafetyTests(unittest.TestCase):
    def test_allows_select_and_select_cte_queries(self):
        self.assertIn(
            "Nexus CRM Suite",
            run_sql_query("SELECT name FROM products LIMIT 1"),
        )
        self.assertIn(
            "Nexus CRM Suite",
            run_sql_query(
                "WITH listed AS (SELECT name FROM products) "
                "SELECT name FROM listed LIMIT 1"
            ),
        )

    def test_rejects_write_and_schema_change_statements(self):
        statements = (
            "DROP TABLE products",
            "DELETE FROM products",
            "UPDATE products SET name = 'changed'",
            "INSERT INTO products VALUES (9, 'test', 'test', 1, 1)",
            "ALTER TABLE products ADD COLUMN extra TEXT",
            "TRUNCATE TABLE products",
            "PRAGMA table_info(products)",
        )
        for statement in statements:
            with self.subTest(statement=statement):
                result = run_sql_query(statement)
                self.assertIn("Only read-only SELECT queries are allowed", result)
                self.assertIn("was not executed", result)

    def test_sqlite_authorizer_rejects_writes_hidden_behind_with(self):
        result = run_sql_query(
            "WITH target AS (SELECT product_id FROM products) "
            "DELETE FROM inventory WHERE product_id IN "
            "(SELECT product_id FROM target)"
        )

        self.assertIn("Only read-only SELECT queries are allowed", result)
        self.assertIn("was not executed", result)

    def test_rejects_select_followed_by_a_write_statement(self):
        result = run_sql_query("SELECT name FROM products; DROP TABLE products;")

        self.assertIn("Only read-only SELECT queries are allowed", result)
        self.assertIn("was not executed", result)

    def test_comments_before_select_are_allowed(self):
        self.assertIn(
            "Nexus CRM Suite",
            run_sql_query("-- read only\nSELECT name FROM products LIMIT 1"),
        )


if __name__ == "__main__":
    unittest.main()
