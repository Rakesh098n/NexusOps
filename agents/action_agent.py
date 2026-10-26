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

from langchain_core.messages import HumanMessage, SystemMessage
from utils.llm import get_llm
from utils.tools import trigger_power_automate
import json
import re


ACTION_SYSTEM_PROMPT = """You are the Action Agent for NexusOps — the final decision layer.

You receive the outputs of three specialist agents:
- Data Analyst (facts & numbers)
- Research Agent (context & root causes)  
- Critic Agent (weaknesses & gaps)

Your job:
1. Synthesise everything into 2-4 SPECIFIC, ACTIONABLE recommendations
2. For each recommendation: state the supporting evidence and expected impact
3. Assign a confidence score (0-100%) based on data quality and critic rating
4. Identify 1-2 immediate next steps (things doable this week)
5. Flag any prerequisite data collection needed before acting

Do NOT repeat all the analysis — be concise and decisive.
Executives need clarity, not summaries of summaries.
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
    llm = get_llm(temperature=0.2)  # Low temp = decisive, consistent outputs

    prompt = f"""Business question: {question}

── Data Analyst Findings ──
{analyst_findings}

── Research Insights ──
{research_insights}

── Critic Review ──
{critic_review}

Produce the final business recommendation. Structure it as:

### 🎯 Executive Summary
[2-3 sentences: situation + key finding + urgency]

### ✅ Recommended Actions
For each action:
- **Action:** [Specific action]
- **Evidence:** [Which agent/data supports this]
- **Expected Impact:** [Quantified if possible]
- **Owner:** [Who in an org should execute this — e.g., Sales Manager, Supply Chain]
- **Timeline:** [This week / This month / Q-level]

### 📊 Confidence Score: [X]%
[Why this score — cite critic's rating]

### ⚡ Immediate Next Steps (This Week)
[2-3 quick wins or data-gathering steps]

### 🚦 Decision: [PROCEED / HOLD / ESCALATE]
[One sentence justifying the decision gate]

Also output a JSON block at the end (for Power Automate) like this:
```json
{{
  "question": "...",
  "decision": "PROCEED/HOLD/ESCALATE",
  "confidence": 75,
  "top_action": "...",
  "urgency": "HIGH/MEDIUM/LOW"
}}
```"""

    response = llm.invoke([
        SystemMessage(content=ACTION_SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ])

    recommendation = response.content

    # ── Extract JSON payload for Power Automate ───────────────────────────────
    pa_status = ""
    if trigger_flow:
        # Pull the JSON block from the LLM's response
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", recommendation, re.DOTALL)
        if json_match:
            try:
                payload = json.loads(json_match.group(1))
                payload["question"] = question  # ensure question is always present
                pa_status = trigger_power_automate(payload)
            except json.JSONDecodeError:
                pa_status = "⚠️ Could not parse payload JSON for Power Automate."
        else:
            pa_status = trigger_power_automate({"question": question, "note": "No JSON extracted"})

    return (
        f"""## 🚀 Action Agent — Final Recommendation\n\n{recommendation}""",
        pa_status,
    )
