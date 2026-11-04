import json
import os
import tempfile
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from server.main import app
from utils.auth import initialize_user_store


class WebApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.environment = patch.dict(
            os.environ,
            {
                "NEXUSOPS_USERS_DB": os.path.join(
                    self.temporary_directory.name, "users.db"
                ),
                "NEXUSOPS_DEMO_MODE": "true",
            },
        )
        self.environment.start()
        initialize_user_store()
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.addCleanup(self.temporary_directory.cleanup)
        self.addCleanup(self.environment.stop)

    def test_health_config_dashboard_and_data_routes(self):
        self.assertEqual(self.client.get("/api/health").json(), {"status": "ok"})
        config = self.client.get("/api/config")
        self.assertEqual(config.status_code, 200)
        self.assertTrue(config.json()["auth_required"])
        self.assertEqual(self.client.get("/api/dashboard").status_code, 401)
        self.login()
        dashboard = self.client.get("/api/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertGreater(dashboard.json()["totals"]["transactions"], 0)
        data = self.client.get("/api/data/customers")
        self.assertEqual(data.status_code, 200)
        self.assertTrue(data.json()["rows"])
        self.assertEqual(self.client.get("/api/data/unknown").status_code, 404)

    def login(self, username="admin", password="admin123"):
        response = self.client.post(
            "/auth/login",
            json={"username": username, "password": password},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["username"], username)

    def test_demo_login_rejects_bad_credentials_and_logout_revokes_access(self):
        failed_login = self.client.post(
            "/auth/login",
            json={"username": "admin", "password": "incorrect"},
        )
        self.assertEqual(failed_login.status_code, 401)
        self.assertEqual(self.client.get("/api/dashboard").status_code, 401)

        self.login()
        self.assertEqual(self.client.get("/api/dashboard").status_code, 200)
        self.assertEqual(self.client.post("/auth/logout").status_code, 200)
        self.assertEqual(self.client.get("/api/dashboard").status_code, 401)

    def test_role_permissions_restrict_raw_data_and_analysis(self):
        self.login("manager", "manager123")
        self.assertEqual(self.client.get("/api/data/customers").status_code, 403)
        manager_scenario = self.client.post(
            "/api/inventory/scenario",
            json={"lead_time_days": 14, "safety_stock_days": 7},
        )
        self.assertEqual(manager_scenario.status_code, 200)
        self.assertTrue(manager_scenario.json()["rows"])
        self.assertEqual(self.client.get("/api/users").status_code, 403)
        manager_dashboard = self.client.get("/api/dashboard").json()
        self.assertTrue(manager_dashboard["inventory"])
        self.client.post("/auth/logout")

        self.login("employee", "employee123")
        self.assertEqual(self.client.get("/api/data/customers").status_code, 403)
        self.assertEqual(
            self.client.post(
                "/api/inventory/scenario",
                json={"lead_time_days": 14, "safety_stock_days": 7},
            ).status_code,
            403,
        )
        self.assertEqual(self.client.get("/api/users").status_code, 403)
        self.assertEqual(
            self.client.post(
                "/api/analyze",
                json={"question": "Who are the top customers by revenue?"},
            ).status_code,
            403,
        )
        employee_dashboard = self.client.get("/api/dashboard").json()
        self.assertEqual(employee_dashboard["inventory"], [])
        self.assertTrue(employee_dashboard["monthly"])

        self.client.post("/auth/logout")
        self.login()
        self.assertEqual(self.client.get("/api/data/customers").status_code, 200)
        invalid_scenario = self.client.post(
            "/api/inventory/scenario",
            json={"lead_time_days": 0, "safety_stock_days": 7},
        )
        self.assertEqual(invalid_scenario.status_code, 422)
        self.assertEqual(self.client.get("/api/users").status_code, 200)

    def test_admin_can_create_and_assign_accounts(self):
        self.login()
        username = f"sales-manager-{uuid.uuid4().hex[:8]}"
        created = self.client.post(
            "/api/users",
            json={
                "username": username,
                "password": "regional-password-123",
                "role": "manager",
            },
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["user"]["role"], "manager")

        updated = self.client.patch(
            f"/api/users/{username}",
            json={"role": "employee"},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["user"]["role"], "employee")
        self.assertEqual(
            self.client.patch(
                f"/api/users/{username}",
                json={"active": False},
            ).json()["user"]["active"],
            False,
        )
        restored = self.client.patch(
            f"/api/users/{username}",
            json={"active": True},
        )
        self.assertTrue(restored.json()["user"]["active"])
        reset = self.client.patch(
            f"/api/users/{username}",
            json={"password": "updated-regional-password"},
        )
        self.assertEqual(reset.status_code, 200)
        self.client.post("/auth/logout")
        self.login(username, "updated-regional-password")

    def test_api_rejects_roles_outside_business_role_set(self):
        self.login()
        created = self.client.post(
            "/api/users",
            json={
                "username": "unsupported-role",
                "password": "secure-password-123",
                "role": "analyst",
            },
        )
        self.assertEqual(created.status_code, 422)

    def test_analysis_stream_contains_stage_and_final_result(self):
        def fake_analysis(
            question,
            use_provider,
            trigger_flow,
            progress_callback,
        ):
            progress_callback("data_analyst", {"analyst_findings": "facts"})
            return {
                "mode": "Groq multi-agent workflow",
                "final_recommendation": "Direct answer",
                "analyst_findings": "facts",
                "error": None,
            }

        with patch("server.main.is_provider_key_configured", return_value=True):
            with patch("server.main.run_business_analysis", side_effect=fake_analysis):
                self.login()
                response = self.client.post(
                    "/api/analyze", json={"question": "Who are the top customers?"}
                )

        self.assertEqual(response.status_code, 200)
        events = [
            json.loads(line[6:])
            for line in response.text.splitlines()
            if line.startswith("data: ")
        ]
        self.assertEqual([event["type"] for event in events], ["progress", "result"])
        self.assertEqual(
            events[-1]["data"]["final_recommendation"], "Direct answer"
        )

    def test_invalid_question_is_rejected(self):
        self.login()
        response = self.client.post("/api/analyze", json={"question": " "})

        self.assertEqual(response.status_code, 422)

    def test_required_auth_blocks_anonymous_api_requests(self):
        response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 401)

    def test_root_serves_built_web_client(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("NexusOps", response.text)
        self.assertIn("assets/", response.text)


if __name__ == "__main__":
    unittest.main()