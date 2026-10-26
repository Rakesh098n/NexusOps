"""
critic_agent.py - Critic Agent
================================
Responsibility: Challenge the combined analysis, find logical flaws,
highlight missing data, and stress-test the reasoning before action is taken.

Interview talking points:
  - The Critic is the most important agent for reducing hallucinations
  - Models the "devil's advocate" or "pre-mortem" technique in management
  - Forces other agents to be specific and evidence-based
  - In real systems, multiple critics can debate (adversarial collaboration)
"""

from langchain_core.messages import HumanMessage, SystemMessage
from utils.llm import get_llm


CRITIC_SYSTEM_PROMPT = """You are the Critic Agent for NexusOps.

Your sole job is to challenge, stress-test, and improve the analysis before any action is taken.

You MUST:
1. Identify logical leaps or assumptions not supported by the data
2. Point out missing data that could change the conclusion
3. Highlight alternative explanations that were ignored
4. Spot any conflicts between the data findings and the research insights
5. Ask the hard questions a CFO or board member would ask

You must NOT:
- Simply agree with everything
- Be vague (say exactly what is weak and why)
- Make up new data

Rate the overall analysis: STRONG / MODERATE / WEAK — and justify it.
Keep response under 400 words.
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
        The Critic Agent implements the "adversarial collaboration" pattern.
        Research shows that adding a critic agent reduces LLM overconfidence
        by ~30-40% in multi-step reasoning tasks. This is why multi-agent
        architectures outperform single-agent + chain-of-thought prompting
        for complex business decisions.
    """
    llm = get_llm(temperature=0.5)  # Higher temp to be creative in finding flaws

    prompt = f"""Original business question: {question}

── Data Analyst Findings ──
{analyst_findings}

── Research Agent Insights ──
{research_insights}

Now critically review the above analysis. Structure your response as:

### ⚠️ Logical Gaps & Assumptions
[List specific assumptions made without sufficient data backing]

### ❓ Missing Data
[What additional data would significantly change or strengthen the conclusion?]

### 🔄 Alternative Explanations
[What other causes could explain the same data that were NOT considered?]

### ⚡ Conflicts & Inconsistencies
[Are there any contradictions between the data findings and research insights?]

### 📋 Hard Questions for Decision-Makers
[3-5 sharp questions a CFO/board member would demand answers to before acting]

### 🏆 Overall Analysis Rating: [STRONG / MODERATE / WEAK]
[One paragraph justifying the rating]"""

    response = llm.invoke([
        SystemMessage(content=CRITIC_SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ])

    return f"""## ⚔️ Critic Agent Review

{response.content}"""
