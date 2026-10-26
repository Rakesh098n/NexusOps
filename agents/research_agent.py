"""
research_agent.py - Research / Context Agent
=============================================
Responsibility: Provide business context, industry best practices,
and broader insights that the raw data alone cannot reveal.

Interview talking points:
  - Complements the Data Analyst: data tells WHAT, Research tells WHY/HOW
  - In production, this would RAG over internal documents / Confluence
  - Kept separate so it can be upgraded (web search, vector DB) independently
"""

from langchain_core.messages import HumanMessage, SystemMessage
from utils.llm import get_llm


RESEARCH_SYSTEM_PROMPT = """You are the Research Agent for NexusOps — a business intelligence platform.

Your role is to provide:
1. Business context and likely root causes based on the data findings
2. Industry best practices relevant to the situation
3. Historical patterns or seasonal factors that explain the data
4. Risks or opportunities that pure data analysis might miss

Rules:
- Base insights on the data analyst's findings + general business knowledge
- Be specific and practical — not generic business jargon
- Acknowledge uncertainty clearly (say "typically" or "research suggests" when appropriate)
- Keep response under 350 words
- Do NOT make a final recommendation — that is the Action Agent's job
"""


def run_research_agent(question: str, analyst_findings: str) -> str:
    """
    Execute the Research Agent to add business context to analyst findings.

    Args:
        question:         Original business question from the user.
        analyst_findings: Output from the Data Analyst Agent.

    Returns:
        String with contextual insights, root-cause hypotheses, and relevant patterns.

    How it works:
        The Research Agent acts like a senior business consultant who reads
        the analyst's report and adds the "why" and "so what" context.
        In a production system, this agent would use RAG (Retrieval Augmented
        Generation) to search company wikis, past reports, and market data.
    """
    llm = get_llm(temperature=0.4)  # Slightly higher creativity for contextual reasoning

    prompt = f"""Business question: {question}

Data Analyst findings:
{analyst_findings}

Based on these findings, provide:
1. **Root Cause Hypotheses** – What business factors likely explain the data?
2. **Industry Context** – What do standard business practices say about this situation?
3. **Risk Factors** – What risks does this data signal?
4. **Opportunities** – Any positive angles or quick wins visible in the data?

Be specific, reference the actual numbers from the findings, and cite common business frameworks where relevant (e.g., seasonality, supply chain, customer lifecycle)."""

    response = llm.invoke([
        SystemMessage(content=RESEARCH_SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ])

    return f"""## 🔍 Research Agent Insights

{response.content}"""
