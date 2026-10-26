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

from langchain_core.messages import HumanMessage, SystemMessage
from utils.llm import get_llm
from utils.tools import run_sql_query, get_database_schema


# System prompt: defines the agent's persona and strict boundaries
DATA_ANALYST_SYSTEM_PROMPT = """You are the Data Analyst Agent for NexusOps.

Your ONLY job is to query the business database and report factual findings.

Rules:
1. Always inspect the schema first, then write targeted SQL queries.
2. Report numbers, trends, and anomalies — do NOT make strategic recommendations.
3. If data is insufficient, say so honestly. Never fabricate numbers.
4. Format output clearly: use bullet points and include the SQL you ran.
5. Keep your response under 400 words.

Database available: SQLite with tables for sales, products, customers, inventory.
"""


def run_data_analyst(question: str, schema: str) -> str:
    """
    Execute the Data Analyst Agent on a business question.

    Args:
        question: The user's business question.
        schema:   Database schema string (pre-fetched for efficiency).

    Returns:
        A string containing SQL queries run, data findings, and brief interpretation.

    How it works:
        1. We give the LLM the schema + question.
        2. LLM decides what SQL to write.
        3. We parse & execute that SQL.
        4. Results are fed back to LLM for interpretation.
        (This two-pass pattern avoids hallucinated data.)
    """
    llm = get_llm(temperature=0.1)  # Low temperature = factual, consistent

    # ── PASS 1: Ask Gemini what SQL to write ──────────────────────────────────
    sql_prompt = f"""Given this database schema:
{schema}

Business question: {question}

Write 1-3 precise SQL SELECT queries to answer this question.
Output ONLY the SQL statements, one per line, no explanation.
Each query must be on its own line starting with 'SELECT'.
Do not use markdown code blocks."""

    sql_response = llm.invoke([
        SystemMessage(content=DATA_ANALYST_SYSTEM_PROMPT),
        HumanMessage(content=sql_prompt)
    ])

    sql_text = sql_response.content.strip()

    # ── Execute each SQL query ────────────────────────────────────────────────
    query_results = []
    lines = sql_text.splitlines()
    current_query = ""
    for line in lines:
        line = line.strip()
        if line.upper().startswith("SELECT"):
            if current_query:
                result = run_sql_query(current_query)
                query_results.append(f"**Query:** `{current_query}`\n**Result:**\n{result}")
            current_query = line
        elif line and current_query:
            current_query += " " + line

    if current_query:
        result = run_sql_query(current_query)
        query_results.append(f"**Query:** `{current_query}`\n**Result:**\n{result}")

    if not query_results:
        # Fallback: try the whole response as one query
        result = run_sql_query(sql_text)
        query_results.append(f"**Query:** `{sql_text}`\n**Result:**\n{result}")

    combined_results = "\n\n".join(query_results)

    # ── PASS 2: Interpret the results ─────────────────────────────────────────
    interpret_prompt = f"""Business question: {question}

Data retrieved from the database:
{combined_results}

Now provide a concise factual analysis of what the data shows.
Focus on: key numbers, trends, anomalies. Do NOT recommend actions yet.
Format with bullet points."""

    interpretation = llm.invoke([
        SystemMessage(content=DATA_ANALYST_SYSTEM_PROMPT),
        HumanMessage(content=interpret_prompt)
    ])

    return f"""## 📊 Data Analyst Findings

{combined_results}

### Interpretation
{interpretation.content}"""
