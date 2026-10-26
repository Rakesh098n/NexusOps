"""
app.py - NexusOps Streamlit Frontend
======================================
Main entry point for the NexusOps multi-agent business intelligence system.

Run with:
    streamlit run app.py

Design principles:
  - Shows agent outputs step-by-step in real-time as they stream
  - Expandable sections so users can drill into any agent's reasoning
  - Clean dark theme with agent-specific colour coding
  - Power Automate toggle for enterprise integration demo
"""

import streamlit as st
import time
import sys
import os

# ── Page config MUST be the very first Streamlit call ────────────────────────
st.set_page_config(
    page_title="NexusOps | Multi-Agent Business Intelligence",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Ensure project root is on Python path ────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from graph.workflow import run_nexus_workflow
from utils.tools import get_database_schema, run_sql_query


# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM CSS — Dark premium theme
# ─────────────────────────────────────────────────────────────────────────────

CUSTOM_CSS = """
<style>
  /* ── Fonts ── */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

  html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
  }

  /* ── Global background ── */
  .stApp {
    background: linear-gradient(135deg, #0a0e1a 0%, #0d1525 50%, #0a0e1a 100%);
    color: #e2e8f0;
  }

  /* ── Header brand ── */
  .nexus-header {
    text-align: center;
    padding: 2rem 0 1rem 0;
  }
  .nexus-logo {
    font-size: 3rem;
    font-weight: 700;
    background: linear-gradient(135deg, #6366f1, #8b5cf6, #06b6d4);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -1px;
  }
  .nexus-tagline {
    color: #64748b;
    font-size: 1rem;
    margin-top: 0.25rem;
    font-weight: 400;
  }

  /* ── Agent cards ── */
  .agent-card {
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    margin: 0.75rem 0;
    border-left: 4px solid;
    backdrop-filter: blur(10px);
    animation: slideIn 0.4s ease-out;
  }
  @keyframes slideIn {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0);    }
  }

  .agent-data     { background: rgba(6, 182, 212, 0.08);  border-color: #06b6d4; }
  .agent-research { background: rgba(139, 92, 246, 0.08); border-color: #8b5cf6; }
  .agent-critic   { background: rgba(245, 158, 11, 0.08); border-color: #f59e0b; }
  .agent-action   { background: rgba(16, 185, 129, 0.08); border-color: #10b981; }

  .agent-label {
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 0.5rem;
  }
  .label-data     { color: #06b6d4; }
  .label-research { color: #8b5cf6; }
  .label-critic   { color: #f59e0b; }
  .label-action   { color: #10b981; }

  /* ── Status pills ── */
  .status-pill {
    display: inline-block;
    padding: 0.2rem 0.75rem;
    border-radius: 999px;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }
  .pill-running  { background: rgba(99, 102, 241, 0.2); color: #818cf8; border: 1px solid #818cf8; }
  .pill-done     { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid #34d399; }
  .pill-error    { background: rgba(239, 68, 68, 0.2);  color: #f87171; border: 1px solid #f87171; }

  /* ── Question input ── */
  .stTextArea textarea {
    background: rgba(15, 23, 42, 0.8) !important;
    border: 1px solid rgba(99, 102, 241, 0.4) !important;
    border-radius: 10px !important;
    color: #e2e8f0 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.95rem !important;
    resize: none !important;
  }
  .stTextArea textarea:focus {
    border-color: #6366f1 !important;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2) !important;
  }

  /* ── Buttons ── */
  .stButton > button {
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    padding: 0.6rem 2rem !important;
    transition: all 0.2s ease !important;
    letter-spacing: 0.02em;
  }
  .stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 8px 25px rgba(99, 102, 241, 0.4) !important;
  }

  /* ── Sidebar ── */
  [data-testid="stSidebar"] {
    background: rgba(10, 14, 26, 0.95) !important;
    border-right: 1px solid rgba(99, 102, 241, 0.15);
  }

  /* ── Metric cards ── */
  [data-testid="metric-container"] {
    background: rgba(15, 23, 42, 0.6) !important;
    border: 1px solid rgba(99, 102, 241, 0.2) !important;
    border-radius: 10px !important;
    padding: 1rem !important;
  }

  /* ── Expander ── */
  .streamlit-expanderHeader {
    background: rgba(15, 23, 42, 0.5) !important;
    border-radius: 8px !important;
    color: #94a3b8 !important;
    font-size: 0.85rem !important;
  }

  /* ── Success/warning/error boxes ── */
  .stSuccess { background: rgba(16, 185, 129, 0.1) !important; }
  .stWarning { background: rgba(245, 158, 11, 0.1) !important; }
  .stError   { background: rgba(239, 68, 68, 0.1) !important;  }

  /* ── Divider ── */
  hr { border-color: rgba(99, 102, 241, 0.15) !important; }

  /* ── Toggle / checkbox ── */
  .stCheckbox label { color: #94a3b8 !important; }

  /* ── Monospace for SQL ── */
  code { font-family: 'JetBrains Mono', monospace !important; }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🧠 NexusOps")
    st.markdown("*Multi-Agent Business Intelligence*")
    st.divider()

    st.markdown("### 🤖 Agent Pipeline")
    agents_info = [
        ("📊", "Data Analyst",  "#06b6d4", "Queries SQLite database for facts & numbers"),
        ("🔍", "Research Agent","#8b5cf6", "Adds business context & root-cause hypotheses"),
        ("⚔️", "Critic Agent",  "#f59e0b", "Challenges weak reasoning & finds data gaps"),
        ("🚀", "Action Agent",  "#10b981", "Synthesises final recommendation"),
    ]
    for icon, name, color, desc in agents_info:
        st.markdown(
            f'<div style="display:flex;align-items:flex-start;margin:0.6rem 0;">'
            f'<span style="font-size:1.2rem;margin-right:0.5rem;">{icon}</span>'
            f'<div><strong style="color:{color}">{name}</strong><br>'
            f'<small style="color:#64748b">{desc}</small></div></div>',
            unsafe_allow_html=True
        )

    st.divider()
    st.markdown("### ⚙️ Settings")
    trigger_flow = st.toggle(
        "🔗 Trigger Power Automate",
        value=False,
        help="Fire a Power Automate webhook with the final recommendation payload"
    )

    st.divider()
    st.markdown("### 💡 Sample Questions")
    sample_questions = [
        "Why did sales drop in March for Nexus CRM Suite?",
        "Which products are at risk of stockout next month?",
        "Should we increase marketing budget for Analytics products?",
        "Who are our top 5 customers by revenue in 2025?",
        "Which region has the lowest sales performance?",
    ]
    for q in sample_questions:
        if st.button(q, key=f"sample_{hash(q)}", use_container_width=True):
            st.session_state["prefill_question"] = q
            st.rerun()

    st.divider()
    st.markdown(
        '<small style="color:#475569">Built with LangGraph + Gemini AI<br>'
        'by Rakesh · NexusOps v1.0</small>',
        unsafe_allow_html=True
    )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN AREA
# ─────────────────────────────────────────────────────────────────────────────

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="nexus-header">'
    '<div class="nexus-logo">⬡ NexusOps</div>'
    '<div class="nexus-tagline">Multi-Agent Business Decision Intelligence · Powered by Gemini AI</div>'
    '</div>',
    unsafe_allow_html=True
)

st.divider()

# ── Metrics row ──────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
with col1: st.metric("🤖 Active Agents", "4", "LangGraph orchestrated")
with col2: st.metric("🗄️ Database Tables", "4", "sales · products · customers · inventory")
with col3: st.metric("🧠 LLM Model", "Gemini 1.5 Flash", "Free tier")
with col4: st.metric("🔗 Integrations", "Power Automate", "Optional webhook")

st.divider()

# ── Question Input ────────────────────────────────────────────────────────────
st.markdown("### 💬 Ask a Business Question")

prefill = st.session_state.pop("prefill_question", "")
question = st.text_area(
    label="Business question",
    value=prefill,
    placeholder="e.g. Why did sales drop in March for Nexus CRM Suite?",
    height=100,
    label_visibility="collapsed",
)

col_btn, col_clear = st.columns([1, 5])
with col_btn:
    run_clicked = st.button("🚀 Analyse", use_container_width=True)
with col_clear:
    if st.button("🗑️ Clear", use_container_width=False):
        st.session_state.pop("last_result", None)
        st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# AGENT EXECUTION
# ─────────────────────────────────────────────────────────────────────────────

def render_agent_output(card_class: str, label_class: str, label: str, content: str):
    """Render a colour-coded agent output card."""
    st.markdown(
        f'<div class="agent-card {card_class}">'
        f'<div class="agent-label {label_class}">{label}</div>'
        f'</div>',
        unsafe_allow_html=True
    )
    st.markdown(content)


if run_clicked and question.strip():
    st.divider()
    st.markdown("## 🔄 Agent Collaboration Pipeline")

    # ── Step trackers ────────────────────────────────────────────────────────
    step_cols = st.columns(4)
    pills = []
    for i, (icon, name, color, _) in enumerate(agents_info):
        with step_cols[i]:
            pill = st.empty()
            pill.markdown(
                f'<div style="text-align:center">'
                f'{icon} <strong style="color:{color}">{name}</strong><br>'
                f'<span class="status-pill pill-running">● Waiting</span>'
                f'</div>',
                unsafe_allow_html=True
            )
            pills.append(pill)

    st.markdown("")

    # ── Output containers ────────────────────────────────────────────────────
    analyst_container  = st.container()
    research_container = st.container()
    critic_container   = st.container()
    action_container   = st.container()
    pa_container       = st.container()

    start_time = time.time()

    # ── Mark agent 1 running ─────────────────────────────────────────────────
    pills[0].markdown(
        '<div style="text-align:center">📊 <strong style="color:#06b6d4">Data Analyst</strong><br>'
        '<span class="status-pill pill-running">⟳ Running...</span></div>',
        unsafe_allow_html=True
    )

    # ── Run full workflow (LangGraph handles all agents sequentially) ─────────
    with st.spinner(""):
        try:
            result = run_nexus_workflow(question.strip(), trigger_flow=trigger_flow)
            st.session_state["last_result"] = result
        except Exception as e:
            st.error(f"❌ Workflow error: {e}")
            st.stop()

    elapsed = round(time.time() - start_time, 1)

    # Handle error state
    if result.get("error"):
        st.error(f"❌ Agent error: {result['error']}")
        st.stop()

    # ── Update all step pills to DONE ─────────────────────────────────────────
    pill_configs = [
        ("📊", "Data Analyst",  "#06b6d4"),
        ("🔍", "Research Agent","#8b5cf6"),
        ("⚔️", "Critic Agent",  "#f59e0b"),
        ("🚀", "Action Agent",  "#10b981"),
    ]
    for i, (icon, name, color) in enumerate(pill_configs):
        pills[i].markdown(
            f'<div style="text-align:center">{icon} <strong style="color:{color}">{name}</strong><br>'
            f'<span class="status-pill pill-done">✓ Done</span></div>',
            unsafe_allow_html=True
        )

    st.success(f"✅ Analysis complete in **{elapsed}s** | All 4 agents collaborated successfully")
    st.divider()

    # ── Render agent outputs in expandable sections ────────────────────────────
    with analyst_container:
        with st.expander("📊 **Data Analyst** — Database Findings", expanded=True):
            st.markdown(
                '<div class="agent-card agent-data">'
                '<div class="agent-label label-data">📊 DATA ANALYST AGENT</div>'
                '</div>',
                unsafe_allow_html=True
            )
            st.markdown(result.get("analyst_findings", "No findings returned."))

    with research_container:
        with st.expander("🔍 **Research Agent** — Business Context & Root Causes", expanded=True):
            st.markdown(
                '<div class="agent-card agent-research">'
                '<div class="agent-label label-research">🔍 RESEARCH AGENT</div>'
                '</div>',
                unsafe_allow_html=True
            )
            st.markdown(result.get("research_insights", "No insights returned."))

    with critic_container:
        with st.expander("⚔️ **Critic Agent** — Critical Review", expanded=True):
            st.markdown(
                '<div class="agent-card agent-critic">'
                '<div class="agent-label label-critic">⚔️ CRITIC AGENT</div>'
                '</div>',
                unsafe_allow_html=True
            )
            st.markdown(result.get("critic_review", "No critique returned."))

    with action_container:
        with st.expander("🚀 **Action Agent** — Final Recommendation", expanded=True):
            st.markdown(
                '<div class="agent-card agent-action">'
                '<div class="agent-label label-action">🚀 ACTION AGENT — FINAL RECOMMENDATION</div>'
                '</div>',
                unsafe_allow_html=True
            )
            st.markdown(result.get("final_recommendation", "No recommendation returned."))

    # ── Power Automate status ─────────────────────────────────────────────────
    if trigger_flow and result.get("power_automate_status"):
        with pa_container:
            st.info(f"🔗 **Power Automate:** {result['power_automate_status']}")

    # ── Elapsed summary ───────────────────────────────────────────────────────
    st.divider()
    st.markdown(
        f'<div style="text-align:center;color:#475569;font-size:0.85rem">'
        f'⏱ Total analysis time: <strong style="color:#6366f1">{elapsed}s</strong> · '
        f'4 agents · Gemini 1.5 Flash · LangGraph StateGraph'
        f'</div>',
        unsafe_allow_html=True
    )

elif run_clicked and not question.strip():
    st.warning("⚠️ Please enter a business question before clicking Analyse.")

# ── Show previous result if not re-running ────────────────────────────────────
elif "last_result" in st.session_state and not run_clicked:
    result = st.session_state["last_result"]
    st.divider()
    st.markdown("## 📋 Previous Analysis (scroll up to ask a new question)")
    with st.expander("📊 Data Analyst Findings", expanded=False):
        st.markdown(result.get("analyst_findings", ""))
    with st.expander("🔍 Research Insights", expanded=False):
        st.markdown(result.get("research_insights", ""))
    with st.expander("⚔️ Critic Review", expanded=False):
        st.markdown(result.get("critic_review", ""))
    with st.expander("🚀 Final Recommendation", expanded=True):
        st.markdown(result.get("final_recommendation", ""))


# ─────────────────────────────────────────────────────────────────────────────
# DATABASE EXPLORER (optional, collapsible at bottom)
# ─────────────────────────────────────────────────────────────────────────────

st.divider()
with st.expander("🗄️ Database Explorer — Browse the underlying business data", expanded=False):
    db_tabs = st.tabs(["📈 Sales (sample)", "📦 Products", "👥 Customers", "🏭 Inventory"])

    with db_tabs[0]:
        st.markdown("**Recent Sales (last 20 rows)**")
        result_sales = run_sql_query(
            "SELECT p.name AS product, c.region, s.sale_date, s.quantity, s.revenue "
            "FROM sales s "
            "JOIN products p ON s.product_id = p.product_id "
            "JOIN customers c ON s.customer_id = c.customer_id "
            "ORDER BY s.sale_date DESC LIMIT 20"
        )
        st.markdown(result_sales)

    with db_tabs[1]:
        st.markdown("**All Products**")
        st.markdown(run_sql_query("SELECT * FROM products"))

    with db_tabs[2]:
        st.markdown("**Customer Segments**")
        st.markdown(run_sql_query(
            "SELECT segment, region, COUNT(*) as count FROM customers GROUP BY segment, region ORDER BY count DESC"
        ))

    with db_tabs[3]:
        st.markdown("**Inventory Status**")
        st.markdown(run_sql_query(
            "SELECT p.name, i.units_in_stock, i.reorder_threshold, "
            "CASE WHEN i.units_in_stock < i.reorder_threshold THEN '⚠️ LOW STOCK' ELSE '✅ OK' END as status "
            "FROM inventory i JOIN products p ON i.product_id = p.product_id"
        ))
