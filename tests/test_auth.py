import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from utils.auth import (
    ROLES,
    authenticate_user,
    create_user,
    initialize_user_store,
    list_users,
    update_user,
)


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.environment = patch.dict(
            os.environ,
            {
                "NEXUSOPS_USERS_DB": str(
                    Path(self.temporary_directory.name) / "users.db"
                ),
                "NEXUSOPS_DEMO_MODE": "true",
            },
            clear=True,
        )
        self.environment.start()
        initialize_user_store()

    def tearDown(self):
        self.environment.stop()
        self.temporary_directory.cleanup()

    def test_demo_role_accounts_have_role_specific_access(self):
        expected = {
            "admin": "admin",
            "manager": "manager",
            "employee": "employee",
        }
        self.assertEqual(ROLES, tuple(expected.values()))
        self.assertEqual(len(list_users()), 3)
        for username, role in expected.items():
            with self.subTest(role=role):
                user = authenticate_user(username, f"{username}123")
                self.assertEqual(user["role"], role)

    def test_passwords_are_stored_as_hashes(self):
        database = Path(os.environ["NEXUSOPS_USERS_DB"])
        stored = database.read_bytes()

        self.assertNotIn(b"admin123", stored)
        self.assertNotIn(b"manager123", stored)

    def test_admin_can_create_update_and_suspend_users(self):
        created = create_user("regional-analyst", "a-strong-password", "employee")
        self.assertEqual(created["role"], "employee")
        self.assertEqual(len(list_users()), 4)

        changed = update_user("regional-analyst", role="manager")
        self.assertEqual(changed["role"], "manager")
        update_user("regional-analyst", password="changed-password-456")
        self.assertIsNone(
            authenticate_user("regional-analyst", "a-strong-password")
        )
        self.assertEqual(
            authenticate_user("regional-analyst", "changed-password-456")["role"],
            "manager",
        )
        suspended = update_user("regional-analyst", active=False)
        self.assertFalse(suspended["active"])
        self.assertIsNone(
            authenticate_user("regional-analyst", "changed-password-456")
        )

    def test_last_admin_cannot_be_removed_or_suspended(self):
        with self.assertRaisesRegex(ValueError, "At least one active administrator"):
            update_user("admin", role="employee")
        with self.assertRaisesRegex(ValueError, "At least one active administrator"):
            update_user("admin", active=False, actor_username="another-admin")

    def test_only_business_roles_can_be_assigned(self):
        with self.assertRaisesRegex(ValueError, "valid workspace role"):
            create_user("old-analyst", "a-strong-password", "analyst")

    def test_existing_analyst_accounts_are_migrated_to_manager(self):
        database = Path(os.environ["NEXUSOPS_USERS_DB"])
        with closing(sqlite3.connect(database)) as connection:
            connection.execute("ALTER TABLE users RENAME TO current_users")
            connection.execute(
                """
                CREATE TABLE users (
                    username TEXT PRIMARY KEY COLLATE NOCASE,
                    password_salt TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(
                        role IN ('admin', 'manager', 'analyst', 'employee')
                    ),
                    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1)),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                "INSERT INTO users VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                ("owner", "salt", "hash", "admin", 1),
            )
            connection.execute(
                "INSERT INTO users VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                ("old-analyst", "salt", "hash", "analyst", 1),
            )
            connection.execute("DROP TABLE current_users")
            connection.commit()

        initialize_user_store()

        migrated_user = next(
            user for user in list_users() if user["username"] == "old-analyst"
        )
        self.assertEqual(migrated_user["role"], "manager")
        with closing(sqlite3.connect(database)) as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO users "
                    "(username, password_salt, password_hash, role) "
                    "VALUES ('invalid', 'salt', 'hash', 'analyst')"
                )

    def test_admin_cannot_suspend_their_own_account(self):
        with self.assertRaisesRegex(ValueError, "cannot deactivate your own"):
            update_user("admin", active=False, actor_username="ADMIN")

    def test_production_requires_configured_bootstrap_credentials(self):
        Path(os.environ["NEXUSOPS_USERS_DB"]).unlink()
        with patch.dict(
            os.environ,
            {"NEXUSOPS_DEMO_MODE": "false"},
            clear=False,
        ):
            os.environ.pop("NEXUSOPS_ADMIN_PASSWORD", None)
            os.environ.pop("NEXUSOPS_ADMIN_USERNAME", None)
            with self.assertRaisesRegex(RuntimeError, "NEXUSOPS_ADMIN_PASSWORD"):
                initialize_user_store()

if __name__ == "__main__":
    unittest.main()
