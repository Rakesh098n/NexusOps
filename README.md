# NexusOps

NexusOps is a business decision-support demo. Its React web workspace and
Streamlit app analyze a seeded SQLite database using deterministic
local analytics or a Groq-backed LangGraph workflow. Results are historical
sample data, not live operational advice.

## What it does

- Answers inventory, customer revenue, regional performance, and sales questions.
- Shows the read-only evidence used to produce an answer.
- Lets Admins and Managers model inventory reorder quantities under adjustable
  supplier lead-time and safety-stock assumptions.
- Offers a four-step analyst, research, critic, and action workflow.
- Requires a username and password before showing the workspace or protected API
  data.
- Provides three business workspace roles with server-enforced least-privilege access and
  an administrator account directory.
- Supports an optional Power Automate HTTP webhook when explicitly configured.

## Architecture

```text
Browser (React/Vite) or Streamlit
                 │
       FastAPI API and signed session
                 │
         Analysis service
          ┌──────┴──────┐
          │             │
      No Groq key     Groq configured
      Local SQL       LangGraph StateGraph
      analytics       Analyst → Research
          │           → Critic → Action
          └──────┬──────┘
                 │
       Read-only sample SQLite
```

In the Groq workflow, the Data Analyst asks Groq for a query and interprets its
results. The SQL executor accepts only `SELECT`/`WITH ... SELECT` statements,
uses a read-only SQLite connection, and installs a SQLite authorizer that
denies writes and schema changes. An unsafe generated statement is not executed
and is reported as an error. The Research Agent adds context, the Critic calls
out uncertainty and data limitations, and the Action Agent synthesizes a
recommendation. Inventory recommendations use deterministic sample-database
facts so a below-threshold result cannot turn into a generic `PROCEED`.

The app falls back to local analytics if `GROQ_API_KEY` is absent or a Groq
request fails, and labels that mode in the UI. The primary web UI is React/Vite
served by FastAPI; `app.py` provides a full Streamlit interface using the same
accounts, role checks, analysis workflow, and sample database.

The generated SQL is executed server-side but is not shown in the employee or
manager-facing findings. They receive the measured result rows and concise
interpretation instead.

The Performance workspace includes an inventory what-if planner. It estimates
target stock as average daily demand multiplied by lead-time plus safety-buffer
days, then subtracts on-hand and on-order units. This is a planning estimate
from the historical sample snapshot, not an order or live forecast; verify
current demand, purchase orders, pack sizes, and supplier constraints before
acting.

## Organization roles

| Role | Workspace access |
|---|---|
| Admin / Owner | Decision desk, performance, read-only data explorer, and user/role administration |
| Manager | Organization-wide decision briefs and aggregated performance/inventory oversight; no raw data explorer |
| Employee | Aggregated sales performance only; no customer-level explorer, inventory detail, or analysis tool |

These are sample-wide permissions. The demo does **not** implement departments,
row-level ownership, multiple companies/tenants, approval workflows, or an audit
log. Before connecting company data, define each organization's data ownership,
manager scope, retention, authorization, and approval policies. The role model
should be extended to enforce those boundaries in the database queries and
identity provider, not just in the navigation.

## Technology

| Technology | Purpose |
|---|---|
| Python 3.11+ | Application and analytics |
| Groq (`langchain-groq` / `ChatGroq`) | Optional LLM provider |
| LangChain | Message and model integration |
| LangGraph | Four-agent workflow orchestration |
| FastAPI + Uvicorn | Authenticated API, streaming, and static web hosting |
| React + Vite | Primary browser interface |
| Streamlit | Alternate authenticated business workspace |
| SQLite + Pandas | Read-only sample data and deterministic analytics |

## Run locally

### 1. Install dependencies

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Push-Location frontend
npm ci
npm run build
Pop-Location
```

For macOS/Linux, activate with `source .venv/bin/activate`.

### 2. Configure credentials and Groq

Copy `.env.example` to `.env`. With `NEXUSOPS_DEMO_MODE=true`, the demo accounts
are:

```text
Admin / Owner: admin / admin123
Manager:       manager / manager123
Employee:      employee / employee123
```

These are demo-only credentials. Before sharing, set
`NEXUSOPS_DEMO_MODE=false`, configure `NEXUSOPS_ADMIN_USERNAME` and a unique
`NEXUSOPS_ADMIN_PASSWORD` of at least 16 characters for the first admin, and
set a random `SESSION_SECRET`. Administrators can then create accounts with
12-character minimum passwords and assign roles in **User access**. Set
`COOKIE_SECURE=true` when serving over HTTPS.

To use the Groq multi-agent workflow, set `GROQ_API_KEY` to a key from
[console.groq.com/keys](https://console.groq.com/keys). `GROQ_MODEL` defaults to
`openai/gpt-oss-20b`. Without a valid key, local sample analytics remain
available and the app explains that Groq is not configured.

### 3. Seed and run

The sample database is included. If it is missing or you intentionally want to
recreate its data, run `python data/seed_database.py` (this resets the sample
tables).

Start the primary web app:

```powershell
python -m uvicorn server.main:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000) and sign in. The API health
check is at `/api/health`.

For frontend hot reload, run `npm run dev` in `frontend/`; Vite proxies API
requests to port 8000. The Streamlit app is started with:

```powershell
python -m streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) for the Streamlit app.
It has the same decision desk, performance view, admin-only data explorer,
account directory, and role access as the web workspace. Both interfaces use
the same SQLite-backed account store at `data/users.db`.
Docker Compose mounts `./data` so locally provisioned accounts survive
container restarts.

## Deploy

### Docker Compose

Set deployment values in an untracked `.env`, including
`NEXUSOPS_DEMO_MODE=false`, `NEXUSOPS_ADMIN_USERNAME`,
`NEXUSOPS_ADMIN_PASSWORD`, and `SESSION_SECRET`. Set
`COOKIE_SECURE=true` behind HTTPS. Add `GROQ_API_KEY` if desired, then run:

```powershell
docker compose up --build -d
```

The app is served on port 8000 (or the configured `PORT`). Do not deploy the
default demo credentials or expose the service over plain HTTP.

### Render

Create a Render Blueprint from this repository. The included `render.yaml`
builds the Docker image, enables secure cookies, and generates a session secret.
Provide `NEXUSOPS_ADMIN_USERNAME`, `NEXUSOPS_ADMIN_PASSWORD`, and (if using
Groq) `GROQ_API_KEY` as Render secrets. For persistence, mount a durable disk at
`/app/data`; without one, accounts created after bootstrap can be lost when an
ephemeral service is replaced. The sample SQLite file is suitable only for the
demo; production deployments need an approved, persistent data source and
appropriate access controls. The current Render Blueprint uses a free
ephemeral service and therefore is a demo deployment, not persistent
organization hosting.

## Reusing NexusOps for another business

The agent pipeline can be reused where a business has structured, queryable
data, but this repository is currently configured for the included sales,
customer, and inventory schema. To adapt it, provide an approved read-only
database connection, document its schema, replace the sample-specific local
analytics and dashboard measures with business-approved KPIs, and define
industry-specific actions and role/data scopes. Retail, distribution, SaaS,
and manufacturing are plausible applications after that data and metric work;
they are not plug-and-play connectors in the current demo.

## Sample questions

- **Which products are at risk of stockout?** The seeded inventory has
  SecureShield Antivirus (12 in stock, threshold 40) and DevOps Pipeline Kit
  (8 in stock, threshold 30), both with no units on order. The action is to
  verify live stock and open orders, then reorder if still below threshold.
- **Who are the top customers by revenue?** Returns the top ten from recorded
  2025 sample sales; the first is Customer_084.
- **Which region has the lowest sales performance?** East has the lowest
  recorded revenue in the sample.
- **Why did sales drop in March for Nexus CRM Suite?**
- **Compare revenue across product categories for Q4 2025.**

Inventory is a snapshot dated 2025-12-01 and sales are synthetic 2025 records.
Verify current source data, demand, supplier lead times, and purchase orders
before taking action.

## Optional Power Automate

Set `POWER_AUTOMATE_WEBHOOK_URL` to a flow's HTTP-trigger URL. The UI only offers
the trigger when both Groq and the webhook are configured, and displays the
HTTP result. Without a URL, no request is sent. Validate webhook permissions
and approval requirements before enabling an external side effect.

## Tests

Run the Python suite from the repository root:

```powershell
python -m unittest discover -s tests
```

Build the web UI:

```powershell
Push-Location frontend
npm run build
Pop-Location
```
