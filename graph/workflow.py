"""
workflow.py - LangGraph Orchestration
======================================
Defines the multi-agent collaboration graph using LangGraph StateGraph.

Architecture:
  User Question
       │
       ▼
  [Data Analyst] ──── queries SQLite ────► findings
       │
       ▼
  [Research Agent] ── adds context ──────► insights
       │
       ▼
  [Critic Agent] ──── challenges ────────► critique
       │
       ▼
  [Action Agent] ──── final decision ────► recommendation
       │
       ▼
  END (returns full state to UI)

Interview talking points:
  - StateGraph passes immutable state between nodes — no shared mutable state
  - Each node is a pure function: (State) → State update dict
  - Graph can be visualised as a DAG — great for explaining to non-technical stakeholders
  - Adding a new agent = add a node + one edge. Zero impact on existing agents.
"""

from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
from utils.tools import get_database_schema
from agents.data_analyst import run_data_analyst
from agents.research_agent import run_research_agent
from agents.critic_agent import run_critic_agent
from agents.action_agent import run_action_agent


# ─────────────────────────────────────────────────────────────────────────────
# STATE SCHEMA
# ─────────────────────────────────────────────────────────────────────────────

class NexusState(TypedDict):
    """
    Shared state that flows between all agents in the graph.

    Each agent reads from state and returns a partial update dict.
    LangGraph merges updates automatically — agents never overwrite each other.

    Interview note:
        TypedDict gives us type-safety without a heavy ORM.
        In production, you'd add fields like: user_id, session_id, audit_log.
    """
    question: str                          # User's original business question
    schema: str                            # DB schema (fetched once, reused)
    analyst_findings: Optional[str]        # Data Analyst output
    research_insights: Optional[str]       # Research Agent output
    critic_review: Optional[str]           # Critic Agent output
    final_recommendation: Optional[str]    # Action Agent output
    power_automate_status: Optional[str]   # PA webhook response
    trigger_flow: bool                     # Whether to fire PA webhook
    error: Optional[str]                   # Any error caught during execution


# ─────────────────────────────────────────────────────────────────────────────
# NODE FUNCTIONS  (each is a pure function: State → dict of updates)
# ─────────────────────────────────────────────────────────────────────────────

def node_data_analyst(state: NexusState) -> dict:
    """Node 1: Run the Data Analyst agent."""
    try:
        findings = run_data_analyst(state["question"], state["schema"])
        return {"analyst_findings": findings}
    except Exception as e:
        return {"error": f"Data Analyst error: {e}"}


def node_research_agent(state: NexusState) -> dict:
    """Node 2: Run the Research agent (uses Data Analyst output)."""
    try:
        insights = run_research_agent(state["question"], state["analyst_findings"])
        return {"research_insights": insights}
    except Exception as e:
        return {"error": f"Research Agent error: {e}"}


def node_critic_agent(state: NexusState) -> dict:
    """Node 3: Run the Critic agent (challenges both previous outputs)."""
    try:
        critique = run_critic_agent(
            state["question"],
            state["analyst_findings"],
            state["research_insights"],
        )
        return {"critic_review": critique}
    except Exception as e:
        return {"error": f"Critic Agent error: {e}"}


def node_action_agent(state: NexusState) -> dict:
    """Node 4: Run the Action agent to produce final recommendation."""
    try:
        recommendation, pa_status = run_action_agent(
            question=state["question"],
            analyst_findings=state["analyst_findings"],
            research_insights=state["research_insights"],
            critic_review=state["critic_review"],
            trigger_flow=state.get("trigger_flow", False),
        )
        return {
            "final_recommendation": recommendation,
            "power_automate_status": pa_status,
        }
    except Exception as e:
        return {"error": f"Action Agent error: {e}"}


def should_continue(state: NexusState) -> str:
    """
    Conditional edge: if an error occurred at any step, skip to END.
    This prevents cascading failures where later agents run on bad data.

    Interview note:
        This is the 'router' pattern in LangGraph — edges can be dynamic.
        In production you'd have more routing logic (e.g., route to a
        'data collection' node if the Critic says data is insufficient).
    """
    if state.get("error"):
        return "end"
    return "continue"


# ─────────────────────────────────────────────────────────────────────────────
# GRAPH ASSEMBLY
# ─────────────────────────────────────────────────────────────────────────────

def build_nexus_graph() -> StateGraph:
    """
    Assemble and compile the NexusOps LangGraph workflow.

    Returns:
        A compiled LangGraph that can be invoked with an initial state dict.

    How to read this graph:
        set_entry_point → data_analyst → research → critic → action → END
        At each step, should_continue() checks for errors and can short-circuit.
    """
    graph = StateGraph(NexusState)

    # Register nodes
    graph.add_node("data_analyst", node_data_analyst)
    graph.add_node("research_agent", node_research_agent)
    graph.add_node("critic_agent", node_critic_agent)
    graph.add_node("action_agent", node_action_agent)

    # Entry point
    graph.set_entry_point("data_analyst")

    # Conditional edges (error check between each step)
    graph.add_conditional_edges(
        "data_analyst",
        should_continue,
        {"continue": "research_agent", "end": END},
    )
    graph.add_conditional_edges(
        "research_agent",
        should_continue,
        {"continue": "critic_agent", "end": END},
    )
    graph.add_conditional_edges(
        "critic_agent",
        should_continue,
        {"continue": "action_agent", "end": END},
    )
    graph.add_edge("action_agent", END)

    return graph.compile()


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def run_nexus_workflow(question: str, trigger_flow: bool = False) -> NexusState:
    """
    Run the full NexusOps multi-agent workflow on a business question.

    Args:
        question:     Business question from the user.
        trigger_flow: Whether to fire the Power Automate webhook at the end.

    Returns:
        Final NexusState with all agent outputs populated.

    Usage:
        state = run_nexus_workflow("Why did sales drop in March?")
        print(state["final_recommendation"])
    """
    # Fetch schema once — all agents share this (avoid redundant DB calls)
    schema = get_database_schema()

    # Build and run the graph
    nexus_graph = build_nexus_graph()
    final_state = nexus_graph.invoke({
        "question": question,
        "schema": schema,
        "analyst_findings": None,
        "research_insights": None,
        "critic_review": None,
        "final_recommendation": None,
        "power_automate_status": None,
        "trigger_flow": trigger_flow,
        "error": None,
    })

    return final_state
