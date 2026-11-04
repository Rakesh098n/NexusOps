"""
tools.py - Shared Tool Utilities
=================================
Helper functions used across multiple agents:
  - SQL query executor (Data Analyst)
  - Schema inspector (Data Analyst)
  - Power Automate webhook trigger (Action Agent)
"""

import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, Optional

import pandas as pd
import requests


# ─────────────────────────────────────────────────────────────────────────────
# 1. DATABASE TOOLS
# ─────────────────────────────────────────────────────────────────────────────

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "sample_business.db")
DB_URI = f"{Path(DB_PATH).resolve().as_uri()}?mode=ro"
_READ_ONLY_SQLITE_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    getattr(sqlite3, "SQLITE_RECURSIVE", -1),
}


def is_power_automate_configured() -> bool:
    return bool(os.getenv("POWER_AUTOMATE_WEBHOOK_URL", "").strip())


def _leading_sql_keyword(query: str) -> str:
    remaining = query.lstrip()
    while remaining:
        if remaining.startswith("--"):
            newline = remaining.find("\n")
            remaining = "" if newline < 0 else remaining[newline + 1 :].lstrip()
        elif remaining.startswith("/*"):
            end_comment = remaining.find("*/", 2)
            if end_comment < 0:
                return ""
            remaining = remaining[end_comment + 2 :].lstrip()
        else:
            break
    match = re.match(r"[A-Za-z]+", remaining)
    return match.group(0).upper() if match else ""


def is_select_query(query: str) -> bool:
    """Return whether a statement starts with SELECT or a SELECT CTE."""
    return _leading_sql_keyword(query) in {"SELECT", "WITH"}


def _split_sql_statements(query: str) -> list[str]:
    statements = []
    current = ""
    for character in query:
        current += character
        if character == ";" and sqlite3.complete_statement(current):
            if current.strip():
                statements.append(current.strip())
            current = ""
    trailing = current.strip()
    if trailing and sqlite3.complete_statement(f"{trailing};"):
        statements.append(trailing)
    return statements


def _read_only_authorizer(
    action: int,
    _argument_one: str | None,
    _argument_two: str | None,
    _database_name: str | None,
    _trigger_name: str | None,
) -> int:
    return (
        sqlite3.SQLITE_OK
        if action in _READ_ONLY_SQLITE_ACTIONS
        else sqlite3.SQLITE_DENY
    )


def run_sql_query(query: str) -> str:
    """
    Execute a read-only SQL query against the SQLite business database.

    Args:
        query: Valid SELECT SQL statement.

    Returns:
        A markdown-formatted table string (or error message).

    Interview note:
        In production this would point at PostgreSQL / Snowflake via SQLAlchemy.
        Swapping is a one-line change in DB_PATH / connection string.
    """
    statements = _split_sql_statements(query)
    if (
        len(statements) != 1
        or not is_select_query(statements[0])
    ):
        return (
            "SQL Error: Only read-only SELECT queries are allowed. "
            "The generated query was not executed."
        )

    try:
        conn = sqlite3.connect(DB_URI, uri=True)
        try:
            conn.set_authorizer(_read_only_authorizer)
            df = pd.read_sql_query(statements[0], conn)
        finally:
            conn.close()
        if df.empty:
            return "Query returned no results."
        return df.to_markdown(index=False)
    except Exception as e:
        if "not authorized" in str(e).casefold():
            return (
                "SQL Error: Only read-only SELECT queries are allowed. "
                "The generated query was not executed."
            )
        return f"SQL Error: {e}"


def get_database_schema() -> str:
    """
    Inspect and return the schema of all tables in the business database.

    Returns:
        Human-readable schema summary listing tables and their columns.

    Interview note:
        The Data Analyst agent calls this first so it knows what columns/tables
        exist before writing SQL — reducing hallucinated column names.
    """
    try:
        conn = sqlite3.connect(DB_URI, uri=True)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            schema_lines = []
            for (table_name,) in tables:
                cursor.execute(f"PRAGMA table_info({table_name});")
                cols = cursor.fetchall()
                col_descriptions = ", ".join(
                    f"{column[1]} ({column[2]})" for column in cols
                )
                schema_lines.append(f"  • {table_name}: [{col_descriptions}]")
        finally:
            conn.close()
        return "Database Schema:\n" + "\n".join(schema_lines)
    except Exception as e:
        return f"Schema Error: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# 2. POWER AUTOMATE WEBHOOK TOOL
# ─────────────────────────────────────────────────────────────────────────────

def trigger_power_automate(payload: Dict[str, Any], webhook_url: Optional[str] = None) -> str:
    """
    Fire a Power Automate HTTP-trigger flow with a JSON payload.

    Args:
        payload:     Dictionary of data to send (e.g., recommendation summary).
        webhook_url: Override the env-var URL for testing.

    Returns:
        Success/failure message string.

    Interview note:
        Power Automate accepts a POST with JSON body. The flow can then send
        emails, create Teams messages, or update SharePoint lists — no extra
        code needed on our side. This is the "bridge to enterprise" pattern.
    """
    url = webhook_url or os.getenv("POWER_AUTOMATE_WEBHOOK_URL", "")
    if not url:
        return "Power Automate webhook URL is not configured; no request was sent."
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code in (200, 202):
            return f"✅ Power Automate flow triggered successfully (HTTP {response.status_code})."
        else:
            return f"❌ Flow trigger failed: HTTP {response.status_code} – {response.text[:200]}"
    except requests.RequestException as e:
        return f"❌ Network error triggering Power Automate: {e}"
