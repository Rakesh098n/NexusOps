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
from utils.llm import get_response_text, invoke_with_fallback


RESEARCH_SYSTEM_PROMPT = """You are NexusOps' business-context analyst.

Use the original question and measured findings as scope. Add context only when
it materially helps answer that question. Label hypotheses as hypotheses and
never present general industry knowledge as a fact about this company. Do not
repeat the data table, add unrelated frameworks, or make recommendations.
If no useful context is supported, say so briefly. Maximum 120 words.
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
    prompt = f"""Business question: {question}

Data Analyst findings:
{analyst_findings}

Provide only context needed to answer the question. Reference a measured value
when useful, label any explanation as an unverified hypothesis, and avoid
generic best practices or unrelated opportunities. If the findings do not
support an explanation, state that clearly."""

    response = invoke_with_fallback([
        SystemMessage(content=RESEARCH_SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ], temperature=0.4)

    return f"""## 🔍 Research Agent Insights

{get_response_text(response)}"""
