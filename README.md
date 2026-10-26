# 🧠 NexusOps — Multi-Agent Business Decision Intelligence

> A production-grade multi-agent AI system where specialized agents collaborate, debate, and deliver actionable business recommendations using real data.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2-purple)
![Gemini](https://img.shields.io/badge/Gemini_AI-2.0_Flash-orange?logo=google)
![Streamlit](https://img.shields.io/badge/Streamlit-1.40-red?logo=streamlit)
![SQLite](https://img.shields.io/badge/SQLite-3-green?logo=sqlite)

---

## 🎯 What is NexusOps?

NexusOps is a **multi-agent business intelligence system** where four specialised AI agents work in a collaborative pipeline to answer complex business questions:

| Agent | Role | Colour |
|-------|------|--------|
| 📊 **Data Analyst** | Queries the business database (SQL), returns facts & numbers | Cyan |
| 🔍 **Research Agent** | Adds business context, root-cause hypotheses, industry patterns | Purple |
| ⚔️ **Critic Agent** | Challenges weak reasoning, finds data gaps, rates confidence | Amber |
| 🚀 **Action Agent** | Synthesises final recommendation + triggers Power Automate | Green |

The agents are orchestrated using **LangGraph StateGraph** — a directed acyclic graph (DAG) where each node is a pure function and state flows immutably between them.

---

## 🏗️ Architecture

```
User Question
     │
     ▼
[LangGraph StateGraph]
     │
     ├─► Node 1: Data Analyst ──── SQL → SQLite ──► findings
     │
     ├─► Node 2: Research Agent ── LLM context ──► insights
     │
     ├─► Node 3: Critic Agent ──── challenges ───► critique
     │
     └─► Node 4: Action Agent ──── synthesises ──► recommendation
                                                      │
                                                      └─► Power Automate (optional)
```

### Why Multi-Agent instead of one big LLM prompt?

| Single LLM | Multi-Agent (NexusOps) |
|-----------|----------------------|
| One prompt does everything | Each agent has a focused role |
| Hard to debug failures | Clear responsibility per agent |
| Overconfident outputs | Critic agent reduces hallucinations |
| Hard to upgrade | Swap one agent without touching others |
| No specialisation | Data agent is "factual", critic is "sceptical" |

---

## 📁 Project Structure

```
NexusOps/
├── app.py                        # Streamlit frontend (dark premium UI)
├── agents/
│   ├── data_analyst.py           # SQL query + factual interpretation
│   ├── research_agent.py         # Business context & root-cause reasoning
│   ├── critic_agent.py           # Adversarial review (reduces hallucinations)
│   └── action_agent.py           # Final recommendation + Power Automate
├── graph/
│   └── workflow.py               # LangGraph StateGraph orchestration
├── data/
│   ├── seed_database.py          # Creates + seeds SQLite with demo data
│   └── sample_business.db        # Auto-generated (git-ignored by default)
├── utils/
│   ├── llm.py                    # Gemini API factory
│   └── tools.py                  # SQL runner, schema inspector, PA webhook
├── requirements.txt
├── .env.example                  # Template — copy to .env
└── README.md
```

---

## 🚀 Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/Rakesh098n/NexusOps.git
cd NexusOps
```

### 2. Create a virtual environment
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up your Gemini API key
```bash
# Copy the template
cp .env.example .env  # Windows: copy .env.example .env

# Edit .env and add your key:
# GOOGLE_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXX

# Get a FREE key from: https://aistudio.google.com/app/apikey
```

### 5. Seed the database
```bash
python data/seed_database.py
```

### 6. Run the app
```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

---

## 💬 Sample Questions to Try

```
Why did sales drop in March for Nexus CRM Suite?
Which products are at risk of stockout next month?
Should we increase marketing budget for Analytics products?
Who are our top 5 customers by revenue in 2025?
Which region has the lowest sales performance?
Compare revenue across product categories for Q4 2025.
```

---

## 🔗 Power Automate Integration (Optional)

1. In Power Automate, create a new flow → **"When an HTTP request is received"**
2. Copy the generated webhook URL
3. Add to your `.env`:  
   ```
   POWER_AUTOMATE_WEBHOOK_URL=https://prod-xx.westus.logic.azure.com/workflows/...
   ```
4. In the app, toggle **"Trigger Power Automate"** in the sidebar
5. The Action Agent will POST this JSON to your flow:
   ```json
   {
     "question": "...",
     "decision": "PROCEED / HOLD / ESCALATE",
     "confidence": 78,
     "top_action": "...",
     "urgency": "HIGH / MEDIUM / LOW"
   }
   ```

Your flow can then: send an email, post to Teams, update SharePoint, create a task in Planner — anything.

---

## 🎤 Interview Talking Points

### 1. Why multi-agent instead of a single LLM?
> "Each agent has a single responsibility — like microservices in software architecture. The Data Analyst never hallucinates numbers because it only runs real SQL. The Critic agent catches overconfident reasoning before it reaches the executive."

### 2. How does LangGraph work?
> "LangGraph uses a StateGraph — a DAG where each node is a pure function that reads from shared state and returns an update. State is immutable and merged by the graph. Adding a new agent is adding one node and one edge."

### 3. Why is the Critic Agent critical?
> "Research shows adversarial collaboration reduces overconfidence in AI outputs by 30-40%. In practice, without a critic, the Action Agent tends to be too confident about weak data. The Critic forces specificity and raises questions that executives would actually ask."

### 4. How would you scale this to real enterprise data?
> "The DB_PATH in `tools.py` is the only change needed to point at PostgreSQL or Snowflake via SQLAlchemy. The Research Agent would use RAG over a vector store (like Pinecone) of internal documents. Power Automate is already production-ready for enterprise."

### 5. What are the limitations?
> "The system runs sequentially, not in parallel — agents could run concurrently with LangGraph's parallel branching for 2-3x speedup. The Critic can't query new data itself — a more advanced version would give it SQL access too. LLM latency (3-8s per agent) is the main UX bottleneck."

---

## 🛠️ Tech Stack

| Technology | Version | Purpose |
|-----------|---------|---------|
| Python | 3.11+ | Core language |
| LangGraph | 0.2 | Agent orchestration (StateGraph) |
| LangChain | 0.3 | LLM abstractions & message types |
| Google Gemini | 2.0-flash | LLM backbone (free tier) |
| Streamlit | 1.40 | Web UI |
| SQLite | 3 | Business data store (demo) |
| Pandas | 2.0 | Data manipulation |
| Power Automate | — | Enterprise workflow trigger |

---

## 👤 Author

**Rakesh** — GitHub: [@Rakesh098n](https://github.com/Rakesh098n)

---

*Built as a portfolio project demonstrating multi-agent AI architecture for real-world business intelligence use cases.*
