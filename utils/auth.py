"""Local user store, password verification, and role permissions."""

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


ROLES = ("admin", "manager", "employee")
ROLE_PERMISSIONS = {
    "admin": ("view_dashboard", "run_analysis", "explore_data", "manage_users"),
    "manager": ("view_dashboard", "run_analysis"),
    "employee": ("view_dashboard",),
}
_PBKDF2_ITERATIONS = 310_000
_DEMO_USERS = (
    ("admin", "admin123", "admin"),
    ("manager", "manager123", "manager"),
    ("employee", "employee123", "employee"),
)


def _database_path() -> Path:
    configured = os.getenv("NEXUSOPS_USERS_DB")
    return Path(configured) if configured else (
        Path(__file__).resolve().parents[1] / "data" / "users.db"
    )


def _connect() -> sqlite3.Connection:
    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def _database_session() -> Iterator[sqlite3.Connection]:
    connection = _connect()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _password_digest(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )


def _insert_user(
    connection: sqlite3.Connection, username: str, password: str, role: str
) -> None:
    salt = secrets.token_bytes(16)
    digest = _password_digest(password, salt)
    connection.execute(
        "INSERT INTO users (username, password_salt, password_hash, role, active) "
        "VALUES (?, ?, ?, ?, 1)",
        (username, salt.hex(), digest.hex(), role),
    )


def _create_user_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE users (
            username TEXT PRIMARY KEY COLLATE NOCASE,
            password_salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'manager', 'employee')),
            active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def initialize_user_store() -> None:
    """Create the user table and bootstrap demo or configured admin access."""
    with _database_session() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "username TEXT PRIMARY KEY COLLATE NOCASE, "
            "password_salt TEXT NOT NULL, password_hash TEXT NOT NULL, "
            "role TEXT NOT NULL CHECK(role IN ('admin', 'manager', 'employee')), "
            "active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1)), "
            "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        schema = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'users'"
        ).fetchone()["sql"]
        if "'analyst'" in schema:
            connection.execute("ALTER TABLE users RENAME TO users_legacy_roles")
            _create_user_table(connection)
            connection.execute(
                "INSERT INTO users (username, password_salt, password_hash, role, "
                "active, created_at) "
                "SELECT username, password_salt, password_hash, "
                "CASE role WHEN 'analyst' THEN 'manager' ELSE role END, "
                "active, created_at FROM users_legacy_roles"
            )
            connection.execute("DROP TABLE users_legacy_roles")

        user_count = connection.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]
        if user_count:
            return

        if demo_mode_enabled():
            for username, password, role in _DEMO_USERS:
                _insert_user(connection, username, password, role)
            return

        username = os.getenv("NEXUSOPS_ADMIN_USERNAME", "").strip()
        password = os.getenv("NEXUSOPS_ADMIN_PASSWORD", "")
        if not username or len(password) < 16:
            raise RuntimeError(
                "Set NEXUSOPS_ADMIN_USERNAME and a NEXUSOPS_ADMIN_PASSWORD "
                "of at least 16 characters for first-time production setup."
            )
        _insert_user(connection, username, password, "admin")


def demo_mode_enabled() -> bool:
    return os.getenv("NEXUSOPS_DEMO_MODE", "true").casefold() in {
        "1", "true", "yes"
    }


def authenticate_user(username: str, password: str) -> dict[str, str] | None:
    """Return an active user after constant-time password hash verification."""
    initialize_user_store()
    with _database_session() as connection:
        row = connection.execute(
            "SELECT username, password_salt, password_hash, role, active "
            "FROM users WHERE username = ? COLLATE NOCASE",
            (username.strip(),),
        ).fetchone()
    if not row or not row["active"]:
        hmac.compare_digest(_password_digest(password, secrets.token_bytes(16)), b"\0" * 32)
        return None

    salt = bytes.fromhex(row["password_salt"])
    candidate = _password_digest(password, salt)
    if not hmac.compare_digest(candidate.hex(), row["password_hash"]):
        return None
    return {"username": row["username"], "role": row["role"]}


def get_active_user(username: str) -> dict[str, str] | None:
    initialize_user_store()
    with _database_session() as connection:
        row = connection.execute(
            "SELECT username, role FROM users "
            "WHERE username = ? COLLATE NOCASE AND active = 1",
            (username,),
        ).fetchone()
    if not row:
        return None
    return {"username": row["username"], "role": row["role"]}


def list_users() -> list[dict[str, Any]]:
    initialize_user_store()
    with _database_session() as connection:
        rows = connection.execute(
            "SELECT username, role, active, created_at FROM users ORDER BY username"
        ).fetchall()
    return [
        {
            "username": row["username"],
            "role": row["role"],
            "active": bool(row["active"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def create_user(username: str, password: str, role: str) -> dict[str, Any]:
    initialize_user_store()
    username = username.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", username):
        raise ValueError(
            "Username must be 1 to 64 letters, numbers, dots, underscores, or hyphens."
        )
    if len(password) < 12:
        raise ValueError("Use a password with at least 12 characters.")
    if role not in ROLES:
        raise ValueError("Choose a valid workspace role.")
    with _database_session() as connection:
        try:
            _insert_user(connection, username, password, role)
        except sqlite3.IntegrityError as error:
            if "users.username" in str(error):
                raise ValueError("That username already exists.") from error
            raise
    return next(user for user in list_users() if user["username"] == username)


def update_user(
    username: str,
    role: str | None = None,
    active: bool | None = None,
    password: str | None = None,
    actor_username: str = "",
) -> dict[str, Any]:
    initialize_user_store()
    if role is not None and role not in ROLES:
        raise ValueError("Choose a valid workspace role.")
    if role is None and active is None and password is None:
        raise ValueError("Provide a role, password, or active-state update.")
    if password is not None and len(password) < 12:
        raise ValueError("Use a password with at least 12 characters.")

    with _database_session() as connection:
        connection.execute("BEGIN IMMEDIATE")
        target = connection.execute(
            "SELECT username, role, active FROM users "
            "WHERE username = ? COLLATE NOCASE",
            (username,),
        ).fetchone()
        if not target:
            raise ValueError("User not found.")
        if target["username"].casefold() == actor_username.casefold() and active is False:
            raise ValueError("You cannot deactivate your own account.")

        next_role = role or target["role"]
        next_active = target["active"] if active is None else int(active)
        remains_admin = next_role == "admin" and bool(next_active)
        if target["role"] == "admin" and target["active"] and not remains_admin:
            other_admin = connection.execute(
                "SELECT 1 FROM users WHERE role = 'admin' AND active = 1 "
                "AND username != ? COLLATE NOCASE LIMIT 1",
                (target["username"],),
            ).fetchone()
            if not other_admin:
                raise ValueError("At least one active administrator must remain.")

        if password is None:
            connection.execute(
                "UPDATE users SET role = ?, active = ? "
                "WHERE username = ? COLLATE NOCASE",
                (next_role, next_active, target["username"]),
            )
        else:
            salt = secrets.token_bytes(16)
            digest = _password_digest(password, salt)
            connection.execute(
                "UPDATE users SET role = ?, active = ?, password_salt = ?, "
                "password_hash = ? WHERE username = ? COLLATE NOCASE",
                (
                    next_role,
                    next_active,
                    salt.hex(),
                    digest.hex(),
                    target["username"],
                ),
            )
    return next(user for user in list_users() if user["username"] == target["username"])
