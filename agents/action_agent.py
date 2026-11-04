"""
action_agent.py - Action Agent
================================
Responsibility: Synthesise all prior agent outputs into a final,
actionable business recommendation and optionally trigger a Power Automate flow.

Interview talking points:
  - Final "synthesis" layer — only agent authorised to recommend actions
  - Explicitly cites which agent's findings support each recommendation
  - Power Automate integration = bridge from AI to real enterprise workflows
  - Confidence scoring makes the uncertainty explicit (important for executives)
"""

import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from utils.llm import get_response_text, invoke_with_fallback
from utils.local_analytics import (
    build_inventory_recommendation,
    get_inventory_snapshot,
)
from utils.tools import trigger_power_automate


ACTION_SYSTEM_PROMPT = """You are the Action Agent for NexusOps — the final decision layer.

You receive the outputs of three specialist agents:
- Data Analyst (facts & numbers)
- Research Agent (context & root causes)  
- Critic Agent (weaknesses & gaps)

Answer the user's original question in concise, professional business language.
Do not use headings such as "Direct answer", "Relevant evidence", or "Next step",
and do not mention agents. Include only information that directly addresses the
question. Offer actions only when asked or when materially necessary. Tie each
action to supplied evidence; never invent impact estimates, owners, or facts.
State important uncertainty clearly.
For inventory or stockout questions, use REORDER when on-hand stock is below
its reorder threshold and no units are on order; use MONITOR when the available
evidence does not justify a new order; use INVESTIGATE when existing orders or
missing information must be checked first. Never use PROCEED. Do not claim
confidence above 90%.
Preserve the date range or snapshot date attached to evidence. If the data is
historical or stale, label it as such and do not present it as current status.
Use concrete measured values and state the historical data scope when relevant.
Do not describe the query, table, or analysis process. Do not repeat findings.
For a direct lookup, ranking, count, or comparison, return only the requested
answer and one essential scope caveat. Do not add a separate evidence or
follow-up section.
"""


def run_action_agent(
    question: str,
    analyst_findings: str,
    research_insights: str,
    critic_review: str,
    trigger_flow: bool = False,
) -> tuple[str, str]:
    """
    Execute the Action Agent to produce the final recommendation.

    Args:
        question:           Original business question.
        analyst_findings:   Data Analyst Agent output.
        research_insights:  Research Agent output.
        critic_review:      Critic Agent output.
        trigger_flow:       If True, fire the Power Automate webhook.

    Returns:
        Tuple of (recommendation_markdown, power_automate_status).

    Interview note:
        Returning a tuple (recommendation, status) keeps the UI layer clean.
        The UI doesn't need to know HOW the recommendation was generated —
        it just displays what it receives. This is the separation-of-concerns
        principle applied to AI agent outputs.
    """
    inventory_question = any(
        term in question.casefold()
        for term in ("stock", "inventory", "reorder", "supply")
    )
    if inventory_question:
        inventory_decision = build_inventory_recommendation(
            get_inventory_snapshot()
        )
        pa_status = ""
        if trigger_flow:
            pa_status = trigger_power_automate(
                {
                    "question": question,
                    "decision": inventory_decision["decision"],
                    "confidence": inventory_decision["confidence"],
                    "top_action": inventory_decision["top_action"],
                    "urgency": inventory_decision["urgency"],
                }
            )
        return (
            inventory_decision["recommendation"],
            pa_status,
        )

    automation_output = (
        "Because Power Automate is enabled, append exactly one JSON block with "
        'keys "question", "decision", "confidence", "top_action", and "urgency". '
        "Use decision REORDER, MONITOR, or INVESTIGATE and urgency HIGH, MEDIUM, "
        "or LOW. Confidence must not exceed 90."
        if trigger_flow
        else "Do not include JSON, code blocks, generic background, or advice unrelated to the question."
    )
    prompt = f"""Business question: {question}

── Data Analyst Findings ──
{analyst_findings}

── Research Insights ──
{research_insights}

── Critic Review ──
{critic_review}

Respond only to the business question above in one concise paragraph or a short
ranked list. Do not add section headings, agent names, process descriptions, or
generic follow-up advice. Include concrete measured values and one brief
historical-scope caveat where necessary. Recommend an action only when the
question asks for one or the evidence shows a material operational issue.

{automation_output}"""

    response = invoke_with_fallback([
        SystemMessage(content=ACTION_SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ], temperature=0.2)

    recommendation = get_response_text(response).strip()
    recommendation = _direct_answer_only(recommendation)
    recommendation = _clean_business_answer(recommendation)

    # ── Extract JSON payload for Power Automate ───────────────────────────────
    pa_status = ""
    if trigger_flow:
        # Pull the JSON block from the LLM's response
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", recommendation, re.DOTALL)
        if not json_match:
            pa_status = (
                "Power Automate was not triggered: the recommendation did not "
                "contain a structured payload."
            )
        else:
            try:
                payload = json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pa_status = "Power Automate was not triggered: payload JSON was invalid."
            else:
                if not isinstance(payload, dict):
                    pa_status = (
                        "Power Automate was not triggered: payload must be a JSON object."
                    )
                else:
                    payload["question"] = question
                    payload["decision"] = _valid_choice(
                        payload.get("decision"),
                        {"REORDER", "MONITOR", "INVESTIGATE"},
                        "INVESTIGATE",
                    )
                    payload["urgency"] = _valid_choice(
                        payload.get("urgency"),
                        {"HIGH", "MEDIUM", "LOW"},
                        "MEDIUM",
                    )
                    try:
                        confidence = int(payload.get("confidence", 85))
                    except (TypeError, ValueError):
                        confidence = 85
                    payload["confidence"] = min(max(confidence, 0), 90)
                    pa_status = trigger_power_automate(payload)

    return (
        recommendation,
        pa_status,
    )


def _direct_answer_only(recommendation: str) -> str:
    """Keep only the requested response when a model adds section headings."""
    match = re.search(
        r"(?ims)^###\s+Direct answer\s*\n(.*?)(?=^###\s+|\Z)",
        recommendation,
    )
    if match:
        return match.group(1).strip()
    return recommendation


def _clean_business_answer(recommendation: str) -> str:
    """Remove internal agent and answer-section labels from user-facing text."""
    cleaned = re.sub(
        r"(?im)^\s*#{1,4}\s*(?:🚀\s*)?Action Agent(?:\s*[—-].*)?$",
        "",
        recommendation,
    )
    cleaned = re.sub(
        r"(?im)^\s*#{1,4}\s*(?:Direct answer|Final recommendation)\s*$",
        "",
        cleaned,
    )
    extra_section = re.search(
        r"(?im)^[ \t]*(?:#{1,4}[ \t]*)?(?:Relevant evidence|Supporting evidence|"
        r"Next steps?|Follow[- ]?up|Additional context)[ \t]*:?[ \t]*$",
        cleaned,
    )
    if extra_section:
        cleaned = cleaned[: extra_section.start()]
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def _valid_choice(value: object, choices: set[str], fallback: str) -> str:
    normalized = str(value).strip().upper()
    return normalized if normalized in choices else fallback
