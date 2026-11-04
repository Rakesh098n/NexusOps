"""
data_analyst.py - Data Analyst Agent
======================================
Responsibility: Translate the business question into SQL queries,
run them against the SQLite database, and return structured findings.

Interview talking points:
  - Uses "tool-calling" pattern: agent decides WHICH queries to run
  - Schema-awareness prevents hallucinated column names
  - Returns raw numbers + brief interpretation (not recommendations)
"""

import re
import sqlite3

from langchain_core.messages import HumanMessage, SystemMessage
from utils.llm import get_response_text, invoke_with_fallback
from utils.tools import is_select_query, run_sql_query


# System prompt: defines the agent's persona and strict boundaries
DATA_ANALYST_SYSTEM_PROMPT = """You are NexusOps' Data Analyst.

Answer only the user's business question using the supplied SQLite schema and
query results. Use the smallest relevant SELECT query or queries. Report facts
with their period and units. Clearly state when the data cannot answer the
question. Do not guess causes, add generic advice, or make recommendations.
Keep the interpretation to at most four concise bullets. Never invent data.
"""


def run_data_analyst(question: str, schema: str) -> str:
    """
    Execute the Data Analyst Agent on a business question.

    Args:
        question: The user's business question.
        schema:   Database schema string (pre-fetched for efficiency).

    Returns:
        Evidence rows and a concise interpretation without exposing generated SQL.

    How it works:
        1. We give the LLM the schema + question.
        2. LLM decides what SQL to write.
        3. We parse & execute that SQL.
        4. Results are fed back to LLM for interpretation.
        (This two-pass pattern avoids hallucinated data.)
    """
    # ── PASS 1: Ask Groq what SQL to write ────────────────────────────────────
    sql_prompt = f"""Given this database schema:
{schema}

Business question: {question}

Write exactly one precise, read-only SQL SELECT statement to answer this
question. Output only that statement, with no alternatives or explanation.
Do not use markdown code blocks."""

    sql_response = invoke_with_fallback([
        SystemMessage(content=DATA_ANALYST_SYSTEM_PROMPT),
        HumanMessage(content=sql_prompt)
    ], temperature=0.1)

    sql_text = get_response_text(sql_response).strip()

    # Split at SQLite statement boundaries in case the model ignores the prompt.
    queries = _split_select_statements(sql_text)
    query_results = []
    if queries:
        query = queries[0]
        result = run_sql_query(query)
        query_results.append(result)
    elif sql_text:
        query_results.append(
            "SQL Error: Only read-only SELECT queries are allowed. "
            "The generated query was not executed."
        )
    else:
        query_results.append(
            "No valid read-only SELECT query was returned for this question."
        )

    combined_results = "\n\n".join(query_results)
    if "SQL Error:" in combined_results:
        return f"""## 📊 Data Analyst Findings

{combined_results}"""

    # ── PASS 2: Interpret the results ─────────────────────────────────────────
    interpret_prompt = f"""Business question: {question}

Data retrieved from the database:
### Observed data

{combined_results}

Answer the user's exact question from these results. Include only relevant
numbers, trends, and caveats. Distinguish measured facts from unknowns. If the
query did not answer the question, say what is missing. Use at most four short
bullets. Do not add general business advice or recommendations."""

    interpretation = invoke_with_fallback([
        SystemMessage(content=DATA_ANALYST_SYSTEM_PROMPT),
        HumanMessage(content=interpret_prompt)
    ], temperature=0.1)

    return f"""## 📊 Data Analyst Findings

### Observed data

{combined_results}

### Interpretation
 {get_response_text(interpretation)}"""


def _split_select_statements(sql_text: str) -> list[str]:
    """Split model output at complete SQLite statement boundaries."""
    cleaned = re.sub(r"```(?:sql)?", "", sql_text, flags=re.IGNORECASE)
    statements = []
    current = ""

    for character in cleaned:
        current += character
        if character == ";" and sqlite3.complete_statement(current):
            statement = current.strip()
            if statement:
                statements.append(statement)
            current = ""

    trailing = current.strip()
    if trailing and sqlite3.complete_statement(f"{trailing};"):
        statements.append(trailing)

    unique_statements = dict.fromkeys(statement.strip() for statement in statements)
    if any(not is_select_query(statement) for statement in unique_statements):
        return []
    return list(unique_statements)
