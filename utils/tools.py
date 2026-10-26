"""
tools.py - Shared Tool Utilities
=================================
Helper functions used across multiple agents:
  - SQL query executor (Data Analyst)
  - Schema inspector (Data Analyst)
  - Power Automate webhook trigger (Action Agent)
"""

import os
import json
import sqlite3
import requests
import pandas as pd
from typing import Any, Dict, Optional


# ─────────────────────────────────────────────────────────────────────────────
# 1. DATABASE TOOLS
# ─────────────────────────────────────────────────────────────────────────────

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "sample_business.db")


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
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(query, conn)
        conn.close()
        if df.empty:
            return "Query returned no results."
        return df.to_markdown(index=False)
    except Exception as e:
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
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        schema_lines = []
        for (table_name,) in tables:
            cursor.execute(f"PRAGMA table_info({table_name});")
            cols = cursor.fetchall()
            col_descriptions = ", ".join(f"{c[1]} ({c[2]})" for c in cols)
            schema_lines.append(f"  • {table_name}: [{col_descriptions}]")
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
        # Simulate the call when no URL is configured (demo mode)
        return (
            "⚠️  Power Automate webhook URL not configured. "
            f"Would have sent payload:\n```json\n{json.dumps(payload, indent=2)}\n```"
        )
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code in (200, 202):
            return f"✅ Power Automate flow triggered successfully (HTTP {response.status_code})."
        else:
            return f"❌ Flow trigger failed: HTTP {response.status_code} – {response.text[:200]}"
    except requests.RequestException as e:
        return f"❌ Network error triggering Power Automate: {e}"
