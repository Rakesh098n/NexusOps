import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ArrowDownToLine,
  ArrowRight,
  BarChart3,
  Check,
  ChevronRight,
  Database,
  FileText,
  LayoutDashboard,
  LoaderCircle,
  LogOut,
  Moon,
  Search,
  ShieldCheck,
  Sparkles,
  Sun,
  TriangleAlert,
  Users,
} from "lucide-react";

const NAV_ITEMS = {
  admin: [
    { name: "Decision desk", icon: LayoutDashboard },
    { name: "Performance", icon: BarChart3 },
    { name: "Data explorer", icon: Database },
    { name: "User access", icon: Users },
  ],
  manager: [
    { name: "Decision desk", icon: LayoutDashboard },
    { name: "Performance", icon: BarChart3 },
  ],
  employee: [{ name: "Performance", icon: BarChart3 }],
};

const ROLE_LABELS = {
  admin: "Admin / Owner",
  manager: "Manager",
  employee: "Employee",
};

const SAMPLE_QUESTIONS = [
  "Which products are at risk of stockout?",
  "Who are our top customers by revenue?",
  "Which region has the lowest sales performance?",
];

const STAGE_LABELS = {
  data_analyst: "Data analysis",
  research_agent: "Business context",
  critic_agent: "Critical review",
  action_agent: "Recommendation",
};

async function getJson(url) {
  const response = await fetch(url, { credentials: "same-origin" });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Request failed (${response.status})`);
  }
  return response.json();
}

function compactMoney(value) {
  const amount = Number(value || 0);
  if (amount >= 1_000_000) return `$${(amount / 1_000_000).toFixed(1)}M`;
  if (amount >= 1_000) return `$${(amount / 1_000).toFixed(1)}K`;
  return `$${amount.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function reportMarkdown(result) {
  return [
    "# NexusOps analysis",
    `Question: ${result.question || ""}`,
    `Mode: ${result.mode || "Groq workflow"}`,
    "## Decision brief",
    result.final_recommendation || "No recommendation returned.",
    "## Evidence",
    result.analyst_findings || "No analyst findings returned.",
    "## Business context",
    result.research_insights || "No business context returned.",
    "## Critical review",
    result.critic_review || "No critical review returned.",
  ].join("\n\n");
}

function App() {
  const [theme, setTheme] = useState(
    () => localStorage.getItem("nexusops-theme") || "light",
  );
  const [page, setPage] = useState("Decision desk");
  const [config, setConfig] = useState(null);
  const [session, setSession] = useState(null);
  const [loginUsername, setLoginUsername] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginRunning, setLoginRunning] = useState(false);
  const [dashboard, setDashboard] = useState(null);
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [activeTab, setActiveTab] = useState("Evidence");
  const [stages, setStages] = useState([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [triggerFlow, setTriggerFlow] = useState(false);
  const [dataset, setDataset] = useState("Sales");
  const [tableData, setTableData] = useState(null);
  const [tableLoading, setTableLoading] = useState(false);
  const [userData, setUserData] = useState(null);
  const [userForm, setUserForm] = useState({
    username: "",
    password: "",
    role: "employee",
  });
  const [userSaving, setUserSaving] = useState(false);
  const [userNotice, setUserNotice] = useState("");

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("nexusops-theme", theme);
  }, [theme]);

  useEffect(() => {
    let cancelled = false;
    async function loadWorkspace() {
      try {
        const [apiConfig, apiSession] = await Promise.all([
          getJson("/api/config"),
          getJson("/api/session"),
        ]);
        if (cancelled) return;
        setConfig(apiConfig);
        setSession(apiSession);
        if (apiConfig.auth_required && !apiSession.user) return;
        if (apiSession.user?.role === "employee") setPage("Performance");
        const apiDashboard = await getJson("/api/dashboard");
        if (cancelled) return;
        setDashboard(apiDashboard);
      } catch (loadError) {
        if (!cancelled) setError(loadError.message);
      }
    }
    loadWorkspace();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (page !== "Data explorer") return;
    let cancelled = false;
    setTableLoading(true);
    getJson(`/api/data/${encodeURIComponent(dataset.toLowerCase())}`)
      .then((payload) => {
        if (!cancelled) setTableData(payload);
      })
      .catch((loadError) => {
        if (!cancelled) setError(loadError.message);
      })
      .finally(() => {
        if (!cancelled) setTableLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [dataset, page]);

  useEffect(() => {
    if (page !== "User access" || session?.user?.role !== "admin") return;
    let cancelled = false;
    getJson("/api/users")
      .then((payload) => {
        if (!cancelled) setUserData(payload);
      })
      .catch((loadError) => {
        if (!cancelled) setError(loadError.message);
      });
    return () => {
      cancelled = true;
    };
  }, [page, session?.user?.role]);

  const totals = dashboard?.totals;
  const stagesByName = useMemo(
    () => new Map(stages.map((stage) => [stage.name, stage])),
    [stages],
  );

  async function submitAnalysis(event) {
    event?.preventDefault();
    if (!question.trim() || running) return;
    setError("");
    setResult(null);
    setStages([]);
    setRunning(true);
    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: question.trim(), trigger_flow: triggerFlow }),
      });
      if (response.status === 401) {
        window.location.assign("/api/session");
        return;
      }
      if (!response.ok || !response.body) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || `Analysis failed (${response.status})`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let finalResult = null;
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() || "";
        for (const block of blocks) {
          const dataLine = block.split("\n").find((line) => line.startsWith("data: "));
          if (!dataLine) continue;
          const message = JSON.parse(dataLine.slice(6));
          if (message.type === "progress") {
            const name = STAGE_LABELS[message.stage] || message.stage;
            setStages((previous) => {
              const current = previous.filter((stage) => stage.name !== name);
              return [...current, { name, error: Boolean(message.error) }];
            });
          } else if (message.type === "result") {
            finalResult = message.data;
            setResult(message.data);
          } else if (message.type === "error") {
            throw new Error(message.message || "The analysis could not be completed.");
          }
        }
      }
      if (!finalResult) throw new Error("The analysis stream ended without a result.");
      setActiveTab("Evidence");
    } catch (analysisError) {
      setError(analysisError.message);
    } finally {
      setRunning(false);
    }
  }

  function downloadReport() {
    if (!result) return;
    const blob = new Blob([reportMarkdown(result)], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "nexusops-analysis.md";
    anchor.click();
    URL.revokeObjectURL(url);
  }

  async function logout() {
    await fetch("/auth/logout", { method: "POST", credentials: "same-origin" });
    setSession({ auth_required: true, user: null });
    setDashboard(null);
    setResult(null);
    window.location.reload();
  }

  async function submitLogin(event) {
    event.preventDefault();
    if (loginRunning) return;
    setError("");
    setLoginRunning(true);
    try {
      const response = await fetch("/auth/login", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: loginUsername,
          password: loginPassword,
        }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.detail || `Sign in failed (${response.status})`);
      }
      setSession({ auth_required: true, user: payload.user });
      setLoginPassword("");
      setPage(payload.user.role === "employee" ? "Performance" : "Decision desk");
      setDashboard(await getJson("/api/dashboard"));
    } catch (loginError) {
      setError(loginError.message);
    } finally {
      setLoginRunning(false);
    }
  }

  async function addWorkspaceUser(event) {
    event.preventDefault();
    setUserSaving(true);
    setUserNotice("");
    try {
      const response = await fetch("/api/users", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(userForm),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.detail || `User creation failed (${response.status})`);
      }
      setUserForm({ username: "", password: "", role: "employee" });
      setUserNotice(`Created ${payload.user.username} as ${ROLE_LABELS[payload.user.role]}.`);
      setUserData(await getJson("/api/users"));
    } catch (userError) {
      setUserNotice(userError.message);
    } finally {
      setUserSaving(false);
    }
  }

  async function updateWorkspaceUser(username, changes) {
    setUserNotice("");
    try {
      const response = await fetch(`/api/users/${encodeURIComponent(username)}`, {
        method: "PATCH",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(changes),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.detail || `User update failed (${response.status})`);
      }
      setUserData(await getJson("/api/users"));
      setUserNotice(`Updated access for ${payload.user.username}.`);
    } catch (userError) {
      setUserNotice(userError.message);
    }
  }

  const navigationItems = NAV_ITEMS[session?.user?.role] || [];

  if (config?.auth_required && !session?.user) {
    return (
      <main className="auth-shell">
        <section className="auth-panel">
          <div className="brand-mark"><Sparkles size={18} /></div>
          <p className="eyebrow">NEXUSOPS / SECURE WORKSPACE</p>
          <h1>Sign in to continue</h1>
          <p>Enter your workspace username and password.</p>
          {error && <div className="notice notice-error"><TriangleAlert size={18} /> {error}</div>}
          <form className="auth-form" onSubmit={submitLogin}>
            <label htmlFor="login-username">Username</label>
            <input id="login-username" autoComplete="username" value={loginUsername} onChange={(event) => setLoginUsername(event.target.value)} required />
            <label htmlFor="login-password">Password</label>
            <input id="login-password" type="password" autoComplete="current-password" value={loginPassword} onChange={(event) => setLoginPassword(event.target.value)} required />
            <button className="primary-button auth-button" type="submit" disabled={loginRunning}>
              {loginRunning ? <LoaderCircle className="spin" size={17} /> : <ArrowRight size={17} />}
              {loginRunning ? "Signing in" : "Sign in"}
            </button>
          </form>
          {config?.demo_mode && <p className="auth-demo">Demo accounts: admin / admin123 · manager / manager123 · employee / employee123</p>}
        </section>
      </main>
    );
  }

  return (
    <div className="app-shell" data-theme={theme}>
      <aside className="sidebar">
        <a className="brand" href="#home" onClick={(event) => { event.preventDefault(); setPage("Decision desk"); }}>
          <span className="brand-mark"><Sparkles size={18} strokeWidth={2.2} /></span>
          <span><strong>NexusOps</strong><small>Decision intelligence</small></span>
        </a>

        <div className="sidebar-label">Workspace</div>
        <nav className="main-nav" aria-label="Workspace">
          {navigationItems.map(({ name, icon: Icon }) => (
            <button className={`nav-item ${page === name ? "active" : ""}`} key={name} onClick={() => setPage(name)}>
              <Icon size={18} strokeWidth={1.9} /> <span>{name}</span>
              {page === name && <ChevronRight className="nav-chevron" size={16} />}
            </button>
          ))}
        </nav>

        <div className="sidebar-spacer" />
        <div className="source-card">
          <span className={`status-dot ${config?.provider_ready ? "online" : "local"}`} />
          <div><strong>{config?.provider_ready ? "Groq connected" : "Local analytics"}</strong><small>Read-only sample database</small></div>
        </div>
        <div className="sidebar-footer">
          <button className="theme-switch" role="switch" aria-checked={theme === "dark"} onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
            <span className="theme-icon">{theme === "dark" ? <Moon size={16} /> : <Sun size={16} />}</span>
            <span>{theme === "dark" ? "Dark mode" : "Light mode"}</span>
            <span className={`switch-track ${theme === "dark" ? "on" : ""}`}><span /></span>
          </button>
          {session?.user && <button className="account-button" onClick={logout}><LogOut size={15} /> Sign out</button>}
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumb"><span>NexusOps</span><ChevronRight size={14} /><strong>{page}</strong></div>
          <div className="topbar-right">
            <span className="source-date">Sample data · through Dec 2025</span>
            {session?.user && <span className="user-chip"><ShieldCheck size={14} /> {session.user.username} · {ROLE_LABELS[session.user.role]}</span>}
          </div>
        </header>

        <div className="page-content">
          <div className="page-heading">
            <div>
              <p className="eyebrow">INTELLIGENCE OPERATIONS</p>
              <h1>{page === "Decision desk" ? "Decision desk" : page}</h1>
              <p className="page-subtitle">
                {page === "Decision desk" && "Ask a business question. Get a concise, evidence-backed decision brief."}
                {page === "Performance" && (session?.user?.role === "employee" ? "Review approved, aggregated business performance." : "Review organization performance and inventory exposure.")}
                {page === "Data explorer" && "Inspect approved, read-only business records behind each analysis."}
                {page === "User access" && "Create accounts, assign least-privilege roles, and suspend workspace access."}
              </p>
            </div>
            {page === "Decision desk" &&             <div className="live-indicator"><span className="pulse-dot" /> {ROLE_LABELS[session?.user?.role]?.toUpperCase()} WORKSPACE</div>}
          </div>

          {error && <div className="notice notice-error"><TriangleAlert size={18} /> {error}</div>}

          {dashboard && <section className="metric-grid" aria-label="Business summary">
            <MetricCard label="Recorded revenue" value={compactMoney(totals?.revenue)} detail="Exact amount available on hover" icon={BarChart3} />
            <MetricCard label="Transactions" value={Number(totals?.transactions || 0).toLocaleString()} detail="Records in sample sales ledger" icon={FileText} />
            <MetricCard label="Customers" value={Number(totals?.customers || 0).toLocaleString()} detail="Distinct customers in sample" icon={Database} />
            <MetricCard label="Latest sale" value={formatMonth(totals?.latest_sale)} detail="Latest record in sample sales" icon={Search} />
          </section>}

          {page === "Decision desk" && <>
            <section className="question-panel">
              <div className="panel-heading">
                <div className="panel-icon"><Sparkles size={17} /></div>
                <div><h2>Ask the business data</h2><p>Answers are grounded in your read-only database.</p></div>
              </div>
              <form onSubmit={submitAnalysis}>
                <label className="sr-only" htmlFor="business-question">Business question</label>
                <textarea id="business-question" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="For example: Which customers generated the most revenue last quarter?" maxLength={1500} rows={3} />
                <div className="question-footer">
                  <span className="input-hint">{question.length}/1500</span>
                  <div className="question-actions">
                    {config?.automation_ready && ["admin", "manager"].includes(session?.user?.role) && <label className="automation-toggle"><input type="checkbox" checked={triggerFlow} onChange={(event) => setTriggerFlow(event.target.checked)} /> <span>Trigger Power Automate</span></label>}
                    <button className="primary-button" type="submit" disabled={running || question.trim().length < 3}>
                      {running ? <LoaderCircle className="spin" size={17} /> : <ArrowRight size={17} />}
                      {running ? "Analyzing" : "Run analysis"}
                    </button>
                  </div>
                </div>
              </form>
              {!config?.provider_ready && <p className="local-note">Using labeled local sample-data analytics. Configure Groq to enable the four-agent workflow.</p>}
              <div className="suggestions">
                <span>Try:</span>
                {SAMPLE_QUESTIONS.map((sample) => <button key={sample} onClick={() => setQuestion(sample)}>{sample}</button>)}
              </div>
            </section>

            {running && <section className="progress-panel" aria-live="polite">
              <div className="progress-title"><span className="pulse-dot" /> Analysis in progress <span className="progress-caption">Stages update as agents finish</span></div>
              <div className="stage-list">
                {["Data analysis", "Business context", "Critical review", "Recommendation"].map((stage) => {
                  const done = stagesByName.has(stage);
                  return <div className={`stage ${done ? "done" : ""}`} key={stage}>{done ? <Check size={15} /> : <span className="stage-pending" />} {stage}</div>;
                })}
              </div>
            </section>}

            {result && <section className="result-section">
              <div className="result-header">
                <div><p className="eyebrow">ANALYSIS RESULT</p><h2>Decision brief</h2></div>
                <button className="secondary-button" onClick={downloadReport}><ArrowDownToLine size={16} /> Download report</button>
              </div>
              {result.fallback_notice && <div className="notice notice-warning"><TriangleAlert size={18} /> {result.fallback_notice}</div>}
              {result.mode === "Local demo analytics" && <div className="notice notice-info"><Database size={17} /> Generated from the included synthetic database; verify against live business systems before acting.</div>}
              {result.power_automate_status && <div className={`notice ${result.power_automate_status.startsWith("✅") ? "notice-info" : "notice-warning"}`}>{result.power_automate_status}</div>}
              <div className="answer-panel"><ReactMarkdown remarkPlugins={[remarkGfm]}>{result.final_recommendation || "No recommendation returned."}</ReactMarkdown></div>
              {session?.user?.role === "admin" && <details className="supporting-analysis">
                <summary>Supporting analysis</summary>
                <div className="result-tabs" role="tablist" aria-label="Analysis detail">
                  {["Evidence", "Business context", "Critical review"].map((tab) => <button role="tab" aria-selected={activeTab === tab} className={activeTab === tab ? "selected" : ""} key={tab} onClick={() => setActiveTab(tab)}>{tab}</button>)}
                </div>
                <div className="detail-panel" role="tabpanel">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{activeTab === "Evidence" ? (result.analyst_findings || "No evidence returned.").replace(/^\s*\*\*Query:\*\*.*(?:\r?\n)+/gim, "") : activeTab === "Business context" ? result.research_insights || "No business context returned." : result.critic_review || "No critical review returned."}</ReactMarkdown>
                </div>
                <div className="result-meta"><span>{result.mode || "Analysis"}</span><span>{Number(result.elapsed_seconds || 0).toFixed(1)} sec</span></div>
              </details>}
            </section>}
          </>}

          {page === "Performance" && dashboard && <PerformanceView dashboard={dashboard} canPlanInventory={["admin", "manager"].includes(session?.user?.role)} />}
          {page === "Data explorer" && session?.user?.permissions?.includes("explore_data") && <DataExplorer dataset={dataset} setDataset={setDataset} data={tableData} loading={tableLoading} />}
          {page === "User access" && session?.user?.role === "admin" && <UserAccessView data={userData} form={userForm} setForm={setUserForm} saving={userSaving} notice={userNotice} onSubmit={addWorkspaceUser} onUpdate={updateWorkspaceUser} />}
          <footer className="page-footer">NexusOps <span>·</span> Decision support, grounded in evidence.</footer>
        </div>
      </main>
    </div>
  );
}

function MetricCard({ label, value, detail, icon: Icon }) {
  return <article className="metric-card" title={detail}><div className="metric-top"><span>{label}</span><Icon size={17} /></div><strong>{value}</strong><small>{detail}</small></article>;
}

function PerformanceView({ dashboard, canPlanInventory }) {
  const maxRevenue = Math.max(...dashboard.monthly.map((item) => Number(item.revenue || 0)), 1);
  return <section className="data-layout">
    <article className="content-panel chart-panel">
      <div className="panel-heading"><div className="panel-icon"><BarChart3 size={17} /></div><div><h2>Monthly revenue</h2><p>Recorded totals by month in the sample dataset.</p></div></div>
      <div className="bar-chart">{dashboard.monthly.map((item) => <div className="bar-row" key={item.month}><span>{item.month}</span><div className="bar-track"><div className="bar-fill" style={{ width: `${Math.max(2, (Number(item.revenue) / maxRevenue) * 100)}%` }} /></div><strong>{compactMoney(item.revenue)}</strong></div>)}</div>
    </article>
    {dashboard.inventory?.length > 0 && <article className="content-panel">
      <div className="panel-heading"><div className="panel-icon"><Database size={17} /></div><div><h2>Inventory exposure</h2><p>Historical snapshot; verify in the live system.</p></div></div>
      <SimpleTable rows={dashboard.inventory} />
      <p className="table-note">Inventory snapshot: {dashboard.inventory[0]?.snapshot_date || "Unknown"}</p>
    </article>}
    {canPlanInventory && <InventoryScenarioPlanner />}
  </section>;
}

function InventoryScenarioPlanner() {
  const [leadTimeDays, setLeadTimeDays] = useState(14);
  const [safetyStockDays, setSafetyStockDays] = useState(7);
  const [scenario, setScenario] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function runScenario(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/inventory/scenario", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lead_time_days: Number(leadTimeDays),
          safety_stock_days: Number(safetyStockDays),
        }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.detail || `Scenario failed (${response.status})`);
      }
      setScenario(payload);
    } catch (scenarioError) {
      setError(scenarioError.message);
    } finally {
      setLoading(false);
    }
  }

  return <article className="content-panel inventory-planner">
    <div className="panel-heading"><div className="panel-icon"><BarChart3 size={17} /></div><div><h2>Inventory what-if planner</h2><p>Estimate replenishment for a chosen supplier lead time and safety buffer.</p></div></div>
    <form className="scenario-controls" onSubmit={runScenario}>
      <label>Lead time (days)<input type="number" min="1" max="365" value={leadTimeDays} onChange={(event) => setLeadTimeDays(event.target.value)} required /></label>
      <label>Safety buffer (days)<input type="number" min="0" max="365" value={safetyStockDays} onChange={(event) => setSafetyStockDays(event.target.value)} required /></label>
      <button className="primary-button" type="submit" disabled={loading}>{loading ? <LoaderCircle className="spin" size={16} /> : <BarChart3 size={16} />}{loading ? "Calculating" : "Run scenario"}</button>
    </form>
    {error && <div className="notice notice-error"><TriangleAlert size={17} /> {error}</div>}
    {scenario && <>
      <p className="table-note">Estimated coverage target uses {scenario.lead_time_days} lead-time days plus {scenario.safety_stock_days} buffer days. Snapshot: {scenario.snapshot_date}.</p>
      <SimpleTable rows={scenario.rows.map((row) => ({
        product: row.product,
        on_hand: row.on_hand,
        on_order: row.on_order,
        average_daily_demand: row.avg_daily_demand.toFixed(1),
        target_stock: row.target_stock,
        suggested_order_quantity: row.suggested_order_quantity,
        decision: row.decision,
      }))} />
      <p className="table-note">Planning estimate only; validate live demand, purchase orders, pack sizes, and supplier constraints before ordering.</p>
    </>}
  </article>;
}

function DataExplorer({ dataset, setDataset, data, loading }) {
  const options = ["Sales", "Products", "Customers", "Inventory"];
  const columns = data?.rows?.length ? Object.keys(data.rows[0]) : [];
  return <section className="content-panel explorer-panel">
    <div className="explorer-heading"><div className="panel-heading"><div className="panel-icon"><Database size={17} /></div><div><h2>Data explorer</h2><p>Read-only sample database records.</p></div></div><label className="dataset-select">Dataset<select value={dataset} onChange={(event) => setDataset(event.target.value)}>{options.map((option) => <option key={option}>{option}</option>)}</select></label></div>
    {loading ? <div className="loading-state"><LoaderCircle className="spin" /> Loading records</div> : <><p className="table-note">Showing {data?.rows?.length?.toLocaleString() || 0} rows from the local SQLite sample.</p><div className="table-wrap"><table><thead><tr>{columns.map((column) => <th key={column}>{column.replaceAll("_", " ")}</th>)}</tr></thead><tbody>{(data?.rows || []).map((row, index) => <tr key={index}>{columns.map((column) => <td key={column}>{String(row[column] ?? "—")}</td>)}</tr>)}</tbody></table></div></>}
  </section>;
}

function SimpleTable({ rows }) {
  const columns = rows?.length ? Object.keys(rows[0]) : [];
  return <div className="table-wrap"><table><thead><tr>{columns.map((column) => <th key={column}>{column.replaceAll("_", " ")}</th>)}</tr></thead><tbody>{(rows || []).map((row, index) => <tr key={index}>{columns.map((column) => <td key={column}>{String(row[column] ?? "—")}</td>)}</tr>)}</tbody></table></div>;
}

function UserAccessView({ data, form, setForm, saving, notice, onSubmit, onUpdate }) {
  const roles = data?.roles || Object.keys(ROLE_LABELS);
  const [passwordDrafts, setPasswordDrafts] = useState({});
  function resetPassword(username) {
    const password = passwordDrafts[username] || "";
    if (password.length < 12) return;
    onUpdate(username, { password }).then(() => {
      setPasswordDrafts({ ...passwordDrafts, [username]: "" });
    });
  }
  return (
    <section className="user-access-layout">
      <article className="content-panel user-create-panel">
        <div className="panel-heading"><div className="panel-icon"><Users size={17} /></div><div><h2>Create workspace account</h2><p>Grant the minimum access needed for each role.</p></div></div>
        <form className="user-create-form" onSubmit={onSubmit}>
          <label>Username<input value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} minLength={1} maxLength={64} required /></label>
          <label>Temporary password<input type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} minLength={12} autoComplete="new-password" required /><small>At least 12 characters. Share credentials securely and rotate them.</small></label>
          <label>Workspace role<select value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })}>{roles.map((role) => <option value={role} key={role}>{ROLE_LABELS[role]}</option>)}</select></label>
          <button className="primary-button" type="submit" disabled={saving}>{saving ? "Creating account…" : "Create account"}</button>
        </form>
      </article>
      <article className="content-panel user-list-panel">
        <div className="panel-heading"><div className="panel-icon"><ShieldCheck size={17} /></div><div><h2>Access directory</h2><p>Role changes and account status apply immediately.</p></div></div>
        {!data ? <div className="loading-state"><LoaderCircle className="spin" /> Loading user directory</div> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Username</th><th>Role</th><th>Status</th><th>Access</th></tr></thead>
              <tbody>{data.users.map((user) => <tr key={user.username}>
                <td>{user.username}</td>
                <td><select className="role-select" aria-label={`Role for ${user.username}`} value={user.role} onChange={(event) => onUpdate(user.username, { role: event.target.value })}>{roles.map((role) => <option value={role} key={role}>{ROLE_LABELS[role]}</option>)}</select></td>
                <td><span className={`user-status ${user.active ? "active" : "inactive"}`}>{user.active ? "Active" : "Suspended"}</span></td>
                <td><div className="user-actions"><button className="secondary-button user-toggle" onClick={() => onUpdate(user.username, { active: !user.active })} disabled={user.username === "admin" && user.active}>{user.active ? "Suspend" : "Restore"}</button><div className="password-reset"><input type="password" aria-label={`Temporary password for ${user.username}`} placeholder="New password (12+)" minLength={12} autoComplete="new-password" value={passwordDrafts[user.username] || ""} onChange={(event) => setPasswordDrafts({ ...passwordDrafts, [user.username]: event.target.value })} /><button className="secondary-button user-toggle" disabled={(passwordDrafts[user.username] || "").length < 12} onClick={() => resetPassword(user.username)}>Reset</button></div></div></td>
              </tr>)}</tbody>
            </table>
          </div>
        )}
        <div className="role-guidance">
          <p><strong>Admin / Owner</strong> — manage accounts, passwords, roles, and all workspace areas.</p>
          <p><strong>Manager</strong> — organization performance and decision briefs; no raw data explorer.</p>
          <p><strong>Employee</strong> — aggregated performance view; no customer-level data or analysis tools.</p>
        </div>
        {notice && <div className={`notice ${notice.startsWith("Created") || notice.startsWith("Updated") ? "notice-info" : "notice-warning"}`}>{notice}</div>}
      </article>
    </section>
  );
}

function formatMonth(value) {
  if (!value) return "—";
  const date = new Date(`${String(value).slice(0, 7)}-01T00:00:00`);
  return date.toLocaleDateString(undefined, { month: "short", year: "numeric" });
}

export default App;
