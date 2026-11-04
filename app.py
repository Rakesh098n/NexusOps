"""NexusOps decision intelligence workspace."""

import time
from datetime import datetime, timezone

import streamlit as st

from utils.analysis_service import run_business_analysis
from utils.auth import (
    ROLES,
    authenticate_user,
    create_user,
    demo_mode_enabled,
    get_active_user,
    list_users,
    update_user,
)
from utils.llm import is_provider_key_configured
from utils.local_analytics import (
    get_dashboard_data,
    get_data_table,
)
from utils.tools import is_power_automate_configured


st.set_page_config(
    page_title="NexusOps | Decision intelligence",
    page_icon=":material/query_stats:",
    layout="wide",
    initial_sidebar_state="expanded",
)

with st.sidebar:
    dark_mode = st.toggle("Dark mode", key="dark_mode", value=False)
    if st.session_state.get("nexusops_user"):
        if st.button("Sign out", key="sign_out"):
            st.session_state.pop("nexusops_user", None)
            st.rerun()
theme_mode = "Dark" if dark_mode else "Light"

THEME_PALETTES = {
        "Light": {
                "background": "#f3f6f3",
                "surface": "#e9efea",
                "panel": "#ffffff",
                "text": "#17231e",
                "muted": "#53645a",
                "border": "#d5ded7",
                "input": "#ffffff",
                "hover": "#e9efea",
        },
        "Dark": {
                "background": "#111915",
                "surface": "#19241e",
                "panel": "#202d25",
                "text": "#e7eee9",
                "muted": "#adbbb1",
                "border": "#39483e",
                "input": "#18221c",
                "hover": "#293a30",
        },
}
ROLE_LABELS = {
    "admin": "Admin / Owner",
    "manager": "Manager",
    "employee": "Employee",
}
theme_colors = THEME_PALETTES[theme_mode]
st.markdown(
        f"""<style>
        :root {{
    color-scheme: {theme_mode.lower()};
            --nexus-bg: {theme_colors['background']};
            --nexus-surface: {theme_colors['surface']};
            --nexus-panel: {theme_colors['panel']};
            --nexus-text: {theme_colors['text']};
            --nexus-muted: {theme_colors['muted']};
            --nexus-border: {theme_colors['border']};
            --nexus-input: {theme_colors['input']};
            --nexus-hover: {theme_colors['hover']};
        }}
        </style>""",
        unsafe_allow_html=True,
)

APP_CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    .stApp { background-color: var(--nexus-bg); color: var(--nexus-text); }
  [data-testid="stSidebar"] {
        background: var(--nexus-surface);
        border-right: 1px solid var(--nexus-border);
        color: var(--nexus-text);
  }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] *,
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] *,
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
        color: var(--nexus-text);
    }
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] { opacity: 0.82; }
    header[data-testid="stHeader"] { background: var(--nexus-bg); }
  .block-container { max-width: 1440px; padding-top: 1.4rem; }
    h1, h2, h3 { color: var(--nexus-text); font-family: 'DM Sans', sans-serif; }
  h1 { font-size: 2rem; font-weight: 700; }
  [data-testid="stMetric"] {
        background: var(--nexus-panel);
        border: 1px solid var(--nexus-border);
    border-radius: 6px;
    padding: 0.9rem 1rem;
  }
    [data-testid="stMetricLabel"] { color: var(--nexus-muted); }
    [data-testid="stMetricValue"] { color: var(--nexus-text); }
    .stButton > button[kind="primary"],
    .stFormSubmitButton > button[kind="primary"],
    .stFormSubmitButton > button[kind="primaryFormSubmit"] {
        background: #176b50 !important;
        border-color: #176b50 !important;
    color: #fff;
  }
  .stButton > button[kind="primary"]:hover,
    .stFormSubmitButton > button[kind="primary"]:hover,
    .stFormSubmitButton > button[kind="primaryFormSubmit"]:hover {
        background: #10563f !important;
        border-color: #10563f !important;
        color: #fff !important;
  }
    .stButton > button[kind="secondary"],
    [data-testid="stDownloadButton"] button[data-testid="stBaseButton-secondary"] {
        background: var(--nexus-panel) !important;
        border: 1px solid var(--nexus-border) !important;
        color: var(--nexus-text) !important;
    }
    .stButton > button[kind="secondary"]:hover,
    [data-testid="stDownloadButton"] button[data-testid="stBaseButton-secondary"]:hover {
        background: var(--nexus-hover) !important;
        border-color: #176b50 !important;
        color: var(--nexus-text) !important;
    }
    [data-testid="stDownloadButton"] button[data-testid="stBaseButton-secondary"] *,
    [data-testid="stDownloadButton"] button[data-testid="stBaseButton-secondary"]:hover * {
        color: inherit !important;
    }
    [data-testid="stWidgetLabel"],
    [data-testid="stWidgetLabel"] p { color: var(--nexus-text) !important; opacity: 1 !important; }
    [data-testid="stCaptionContainer"] { color: var(--nexus-muted); }
    [data-testid="stTooltipContent"],
    [data-testid="stTooltipContent"] * { background-color: #17231e !important; color: #fff !important; }
  .stTextArea textarea, .stTextInput input {
        background: var(--nexus-input);
        color: var(--nexus-text);
        border-color: var(--nexus-border);
    border-radius: 5px;
  }
    [data-testid="stDataFrame"] { border: 1px solid var(--nexus-border); }
  code, pre { font-family: 'IBM Plex Mono', monospace; }
  .workspace-kicker {
    color: #176b50;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.76rem;
    text-transform: uppercase;
  }
    .workspace-note { color: var(--nexus-muted); font-size: 0.92rem; }
  .login-panel {
    max-width: 560px;
    margin: 12vh auto 0 auto;
    padding: 2.2rem;
    background: var(--nexus-panel);
    color: var(--nexus-text);
    border: 1px solid var(--nexus-border);
    border-top: 4px solid #176b50;
  }
  @media (max-width: 700px) {
    .block-container { padding: 1rem 1rem 2rem 1rem; }
    h1 { font-size: 1.65rem; }
  }
</style>
"""
st.markdown(APP_CSS, unsafe_allow_html=True)


def _enforce_authentication():
    username = st.session_state.get("nexusops_user")
    if username:
        user = get_active_user(username)
        if user:
            return user
        st.session_state.pop("nexusops_user", None)

    st.markdown(
        '<div class="login-panel">'
        '<div class="workspace-kicker">NexusOps / secure workspace</div>'
        '<h1>Sign in to continue</h1>'
        '<p class="workspace-note">Sign in to access the business analysis workspace.</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    with st.form("nexusops_login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary")
    if demo_mode_enabled():
        st.caption("Demo accounts: admin / admin123 · manager / manager123 · employee / employee123")
    if submitted:
        user = authenticate_user(username, password)
        if user:
            st.session_state["nexusops_user"] = user["username"]
            st.rerun()
        st.error("Invalid username or password.")
    st.stop()


current_user = _enforce_authentication()
has_provider_key = is_provider_key_configured()


@st.cache_data(ttl=300)
def _load_dashboard_data():
    return get_dashboard_data()


def _render_header(title: str, subtitle: str):
    st.markdown('<div class="workspace-kicker">NexusOps / intelligence operations</div>',
                unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<div class="workspace-note">{subtitle}</div>',
                unsafe_allow_html=True)


def _render_kpis(data: dict):
    totals = data["totals"]
    first_row = st.columns(2)
    revenue = float(totals["revenue"])
    compact_revenue = (
        f"${revenue / 1_000_000:.1f}M"
        if revenue >= 1_000_000
        else f"${revenue / 1_000:.1f}K"
        if revenue >= 1_000
        else f"${revenue:,.0f}"
    )
    first_row[0].metric(
        "Recorded revenue",
        compact_revenue,
        help=f"Exact sample total: ${revenue:,.2f}",
    )
    first_row[1].metric("Transactions", f"{totals['transactions']:,}")
    second_row = st.columns(2)
    second_row[0].metric("Customers", f"{totals['customers']:,}")
    latest_month = datetime.strptime(
        str(totals["latest_sale"]), "%Y-%m-%d"
    ).strftime("%b %Y")
    second_row[1].metric("Latest sale", latest_month)


def _format_error(error: str) -> str:
    normalized = error.casefold()
    if "503" in normalized or "unavailable" in normalized:
        return (
            "Groq is temporarily unavailable. Retry shortly; local analytics "
            "is still available."
        )
    if "api key" in normalized or "api_key" in normalized:
        return "Groq rejected the API key. Check GROQ_API_KEY in your local .env file."
    if "429" in normalized or "resource_exhausted" in normalized:
        return "Groq quota is currently exhausted. Check the Groq console or try again later."
    if "timeout" in normalized or "timed out" in normalized:
        return "The model request timed out. Retry once, or use local demo analytics meanwhile."
    if "404" in normalized or "not found" in normalized:
        return "The selected Groq model is unavailable for this key. Check GROQ_MODEL."
    return "The analysis stopped before all stages completed. Any completed evidence is shown below."


def _render_results(result: dict, show_supporting_analysis: bool):
    error = result.get("error")
    if error:
        st.error(_format_error(str(error)), icon=":material/error:")
        with st.expander("Technical details"):
            st.code(str(error))
    elif result.get("fallback_notice"):
        st.warning(
            result["fallback_notice"],
            icon=":material/sync_problem:",
        )
    elif result.get("mode") == "Local demo analytics":
        st.info(
            "Generated from the included synthetic database. Results are historical "
            "and must be checked against live business systems before decisions.",
            icon=":material/info:",
        )

    st.subheader("Decision brief")
    if result.get("final_recommendation"):
        st.markdown(result["final_recommendation"])
    elif error:
        st.caption("No recommendation was generated because the workflow stopped early.")

    if show_supporting_analysis:
        with st.expander("Supporting analysis"):
            evidence_tab, context_tab, review_tab = st.tabs(
                ["Evidence", "Business context", "Critical review"]
            )
            with evidence_tab:
                st.markdown(result.get("analyst_findings") or "No analyst findings were returned.")
            with context_tab:
                st.markdown(result.get("research_insights") or "No research context was returned.")
            with review_tab:
                st.markdown(result.get("critic_review") or "No critical review was returned.")

    report = "\n\n".join(
        [
            f"# NexusOps analysis\n\nQuestion: {result.get('question', '')}",
            f"Mode: {result.get('mode', 'AI multi-agent workflow')}",
            "## Decision brief\n\n" + str(result.get("final_recommendation", "")),
            "## Evidence\n\n" + str(result.get("analyst_findings", "")),
            "## Business context\n\n" + str(result.get("research_insights", "")),
            "## Critical review\n\n" + str(result.get("critic_review", "")),
        ]
    )
    st.download_button(
        "Download analysis report",
        data=report,
        file_name="nexusops-analysis.md",
        mime="text/markdown",
        icon=":material/download:",
    )
    if result.get("completed_at"):
        st.caption(
            f"Completed {result['completed_at']} · {result.get('elapsed_seconds', 0):.1f}s"
        )


with st.sidebar:
    st.markdown("## NexusOps")
    st.caption("Business decision intelligence")
    st.divider()
    role = current_user["role"]
    role_pages = {
        "admin": ["Decision desk", "Performance", "Data explorer", "User access"],
        "manager": ["Decision desk", "Performance"],
        "employee": ["Performance"],
    }
    available_pages = role_pages[role]
    if st.session_state.get("workspace_page") not in available_pages:
        st.session_state["workspace_page"] = available_pages[0]
    page = st.radio(
        "Workspace",
        available_pages,
        key="workspace_page",
        label_visibility="collapsed",
    )
    st.divider()
    if has_provider_key:
        st.badge("Groq enabled", icon=":material/bolt:", color="green")
    else:
        st.badge("Local demo mode", icon=":material/database:", color="orange")
    st.caption("Read-only SQLite source · sample data through Dec 2025")
    st.caption(
        f"Signed in as {current_user['username']} · "
        f"{ROLE_LABELS[current_user['role']]}"
    )
    trigger_flow = False
    if (
        has_provider_key
        and is_power_automate_configured()
        and role in {"admin", "manager"}
    ):
        st.divider()
        trigger_flow = st.toggle(
            "Trigger Power Automate",
            value=False,
            help="Send the final recommendation to the configured webhook.",
        )


if page == "Decision desk":
    _render_header(
        "Decision desk",
        "Ask a business question, inspect the evidence, and review the decision before acting.",
    )
    try:
        dashboard_data = _load_dashboard_data()
        _render_kpis(dashboard_data)
    except Exception as exc:
        st.error(f"Business data could not be loaded: {exc}")
        st.stop()

    st.subheader("Ask the business data")
    if not has_provider_key:
        st.info(
            "Local analytics is active. Add GROQ_API_KEY to .env to enable the "
            "four-agent Groq workflow; the local mode below still returns "
            "database-backed answers.",
            icon=":material/info:",
        )

    sample_questions = [
        "Which products are at risk of stockout?",
        "Who are our top customers by revenue?",
        "Which region has the lowest sales performance?",
    ]
    sample_columns = st.columns(3)
    for index, sample in enumerate(sample_questions):
        if sample_columns[index].button(
            sample,
            key=f"sample_{index}",
            width="stretch",
        ):
            st.session_state["business_question"] = sample
            st.rerun()

    with st.form("analysis_form"):
        question = st.text_area(
            "Business question",
            key="business_question",
            placeholder="For example: Which products have the lowest stock coverage?",
            height=105,
        )
        submitted = st.form_submit_button(
            "Run analysis",
            type="primary",
            icon=":material/arrow_forward:",
            width="stretch",
        )

    if submitted:
        if not question.strip():
            st.warning("Enter a business question to start the analysis.")
        else:
            started = time.perf_counter()
            progress = st.status("Preparing business analysis", expanded=True)
            try:
                if has_provider_key:
                    progress.write("Connecting to the configured Groq model...")

                    def report_progress(node_name: str, update: dict):
                        names = {
                            "data_analyst": "Data analysis",
                            "research_agent": "Business context",
                            "critic_agent": "Critical review",
                            "action_agent": "Recommendation synthesis",
                        }
                        stage = names.get(node_name, node_name.replace("_", " ").title())
                        if update.get("error"):
                            progress.update(
                                label=f"{stage} stopped with an error",
                                state="error",
                                expanded=True,
                            )
                            progress.write(str(update["error"]))
                        else:
                            progress.write(f"Completed: {stage}")
                            progress.update(label=f"Completed: {stage}", state="running")

                    result = run_business_analysis(
                        question=question.strip(),
                        use_provider=True,
                        trigger_flow=trigger_flow,
                        progress_callback=report_progress,
                    )
                else:
                    progress.write("Running read-only queries against the sample database...")
                    result = run_business_analysis(
                        question=question.strip(),
                        use_provider=False,
                    )
                result["question"] = question.strip()
                result["elapsed_seconds"] = time.perf_counter() - started
                result["completed_at"] = datetime.now(timezone.utc).strftime(
                    "%Y-%m-%d %H:%M UTC"
                )
                progress.update(
                    label=(
                        "Local answer returned after Groq failure"
                        if result.get("fallback_notice")
                        else "Analysis finished"
                        if not result.get("error")
                        else "Analysis stopped"
                    ),
                    state="complete" if not result.get("error") else "error",
                    expanded=bool(result.get("error")),
                )
                st.session_state["analysis_result"] = result
            except Exception as exc:
                if has_provider_key:
                    result = run_business_analysis(
                        question=question.strip(),
                        use_provider=False,
                    )
                    result["mode"] = "Local fallback analytics"
                    result["fallback_notice"] = (
                        "Groq could not complete this request. The answer below "
                        "uses the included sample database instead."
                    )
                    result["question"] = question.strip()
                    result["elapsed_seconds"] = time.perf_counter() - started
                    result["completed_at"] = datetime.now(timezone.utc).strftime(
                        "%Y-%m-%d %H:%M UTC"
                    )
                    st.session_state["analysis_result"] = result
                    progress.update(
                        label="Local answer returned after Groq failure",
                        state="complete",
                        expanded=True,
                    )
                else:
                    progress.update(label="Analysis failed", state="error", expanded=True)
                    progress.write(_format_error(str(exc)))
                    st.session_state["analysis_result"] = {
                        "question": question.strip(),
                        "error": str(exc),
                        "mode": "Local demo analytics",
                        "elapsed_seconds": time.perf_counter() - started,
                        "completed_at": datetime.now(timezone.utc).strftime(
                            "%Y-%m-%d %H:%M UTC"
                        ),
                    }

    if "analysis_result" in st.session_state:
        st.divider()
        _render_results(
            st.session_state["analysis_result"],
            show_supporting_analysis=role == "admin",
        )

elif page == "Performance":
    _render_header(
        "Performance",
        "Review recorded sales activity and inventory exposure in the included sample dataset.",
    )
    try:
        dashboard_data = _load_dashboard_data()
    except Exception as exc:
        st.error(f"Business data could not be loaded: {exc}")
        st.stop()

    _render_kpis(dashboard_data)
    st.subheader("Monthly revenue")
    st.line_chart(
        dashboard_data["monthly"].set_index("month")["revenue"],
        height=300,
        y_label="Revenue",
    )
    if role in {"admin", "manager"}:
        st.subheader("Inventory coverage")
        inventory = dashboard_data["inventory"].copy()
        inventory["status"] = inventory.apply(
            lambda row: "Reorder review"
            if row["units_in_stock"] < row["reorder_threshold"]
            or row["days_of_cover"] <= 30
            else "Within threshold",
            axis=1,
        )
        st.dataframe(inventory, hide_index=True, width="stretch")
        snapshot_date = inventory["snapshot_date"].max()
        st.caption(
            f"Inventory snapshot: {snapshot_date}. Sample sales end on "
            f"{dashboard_data['totals']['latest_sale']}; these are not live operational feeds."
        )

elif page == "Data explorer" and role == "admin":
    _render_header(
        "Data explorer",
        "Inspect the read-only business dataset used to produce analysis evidence.",
    )
    dataset = st.selectbox("Dataset", ["Sales", "Products", "Customers", "Inventory"])
    rows = get_data_table(dataset)
    st.caption(f"Showing {len(rows):,} rows · source: local SQLite sample database")
    st.dataframe(rows, hide_index=True, width="stretch", height=560)
elif page == "User access" and role == "admin":
    _render_header(
        "User access",
        "Create staff accounts and manage their business workspace access.",
    )
    notice = st.session_state.pop("workspace_user_notice", None)
    if notice:
        st.success(notice)
    with st.form("create_workspace_user"):
        st.subheader("Create workspace account")
        new_username = st.text_input("Username")
        new_password = st.text_input(
            "Temporary password",
            type="password",
            help="Use at least 12 characters.",
        )
        new_role = st.selectbox(
            "Role",
            ROLES,
            index=ROLES.index("employee"),
            format_func=lambda value: ROLE_LABELS[value],
        )
        create_submitted = st.form_submit_button("Create account", type="primary")
    if create_submitted:
        try:
            created_user = create_user(new_username, new_password, new_role)
            st.session_state["workspace_user_notice"] = (
                f"Created {created_user['username']} as "
                f"{ROLE_LABELS[created_user['role']]}."
            )
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

    st.subheader("Access directory")
    for workspace_user in list_users():
        with st.expander(
            f"{workspace_user['username']} · "
            f"{'Active' if workspace_user['active'] else 'Suspended'}"
        ):
            with st.form(f"update_workspace_user_{workspace_user['username']}"):
                selected_role = st.selectbox(
                    "Role",
                    ROLES,
                    index=ROLES.index(workspace_user["role"]),
                    format_func=lambda value: ROLE_LABELS[value],
                )
                active = st.checkbox(
                    "Account active",
                    value=workspace_user["active"],
                )
                replacement_password = st.text_input(
                    "New password (optional)",
                    type="password",
                    help="Leave blank to keep the current password; new passwords need 12 characters.",
                )
                save_user = st.form_submit_button("Save access changes")
            if save_user:
                try:
                    update_user(
                        workspace_user["username"],
                        role=selected_role,
                        active=active,
                        password=replacement_password or None,
                        actor_username=current_user["username"],
                    )
                    st.session_state["workspace_user_notice"] = (
                        "Workspace access updated."
                    )
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))