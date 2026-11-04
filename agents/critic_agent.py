"""
critic_agent.py - Critic Agent
================================
Responsibility: Challenge the combined analysis, find logical flaws,
highlight missing data, and stress-test the reasoning before action is taken.

Interview talking points:
  - The Critic highlights unsupported claims and material data gaps
  - Models the "devil's advocate" or "pre-mortem" technique in management
  - Forces other agents to be specific and evidence-based
  - In real systems, multiple critics can debate (adversarial collaboration)
"""

import re

from langchain_core.messages import HumanMessage, SystemMessage
from utils.llm import get_response_text, invoke_with_fallback


CRITIC_SYSTEM_PROMPT = """You are NexusOps' evidence reviewer.

Review only claims that affect the user's specific question. Identify concrete
unsupported claims, material missing data, or contradictions. Do not invent
facts, repeat the analysis, or add generic boardroom questions. If no material
issue exists, say so. Give a concise confidence rating and keep the review under
120 words. Never give a confidence rating above 90%. For inventory questions,
explicitly account for the snapshot date and missing current demand, supplier
lead-time, and purchase-order information.
"""


def run_critic_agent(question: str, analyst_findings: str, research_insights: str) -> str:
    """
    Execute the Critic Agent to challenge and validate the combined analysis.

    Args:
        question:           Original business question.
        analyst_findings:   Data Analyst Agent output.
        research_insights:  Research Agent output.

    Returns:
        Critical review including identified weaknesses, missing data,
        alternative explanations, and an overall confidence rating.

    Interview note:
        The Critic identifies unsupported claims and missing evidence; its
        review is a safeguard, not a guarantee against hallucinations.
    """
    prompt = f"""Original business question: {question}

── Data Analyst Findings ──
{analyst_findings}

── Research Agent Insights ──
{research_insights}

Review whether the answer is supported and relevant to the original question.
Return only material issues or missing data, then a confidence rating. If there
are no material issues, say that in one sentence. Do not add generic questions
or repeat prior findings."""

    response = invoke_with_fallback([
        SystemMessage(content=CRITIC_SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ], temperature=0.5)

    review = get_response_text(response).strip()
    review = _bound_confidence_rating(review)
    inventory_question = any(
        term in question.casefold()
        for term in ("stock", "inventory", "reorder", "supply")
    )
    if inventory_question:
        missing_data = (
            "The 2025-12-01 snapshot lacks current demand, supplier lead times, "
            "and verified purchase-order status."
        )
        if not all(
            term in review.casefold()
            for term in ("demand", "lead time", "purchase order")
        ):
            review = f"{review}\n\nData limitation: {missing_data}"
    else:
        missing_data = (
            "The synthetic 2025 sample is historical and cannot establish current "
            "conditions or business causes."
        )
        if not any(
            term in review.casefold()
            for term in (
                "limitation",
                "historical",
                "missing",
                "lacks",
                "cannot establish",
            )
        ):
            review = f"{review}\n\nData limitation: {missing_data}"

    return f"""## ⚔️ Critic Agent Review

{review}"""


def _bound_confidence_rating(review: str) -> str:
    """Keep numeric confidence claims below 100%, adding a rating if omitted."""
    pattern = re.compile(
        r"(?i)(\bconfidence\b[^\d\n]{0,20})(\d{1,3})\s*%"
        r"|(\d{1,3})\s*%\s*(\bconfidence\b)"
    )

    def replace_rating(match: re.Match[str]) -> str:
        value = int(match.group(2) or match.group(3))
        value = min(value, 90)
        if match.group(2):
            return f"{match.group(1)}{value}%"
        return f"{value}% {match.group(4)}"

    bounded = pattern.sub(replace_rating, review)
    bounded = re.sub(
        r"(?i)\b100\s*%(?=\s*(?:confiden\w*|certain\w*|sure\b))",
        "90%",
        bounded,
    )
    if not re.search(r"(?i)\bconfiden(?:ce|t)\b", bounded):
        bounded = f"{bounded}\n\nConfidence: 85%."
    return bounded
