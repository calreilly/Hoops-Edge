# Hoops Edge — Project Specification

**Course:** GRAD5900  
**Student:** Cal Reilly  
**Project:** AI-Powered College Basketball +EV Betting Agent  
**Repo:** [github.com/calreilly/Hoops-Edge](https://github.com/calreilly/Hoops-Edge)

---

## Project Overview

Hoops Edge is an autonomous AI agent that identifies positive expected value (+EV) betting opportunities in college basketball (NCAAB) by combining live sportsbook odds, team performance metrics, and chain-of-thought LLM reasoning. The system applies Kelly Criterion position sizing, maintains a persistent bet ledger, and provides a real-time interactive dashboard for bet review and approval.

The project demonstrates a full agentic AI stack: structured LLM output, RAG pipelines, multi-agent coordination, external API integration, and human-in-the-loop decision making.

---

## Architecture Overview

```
The-Odds-API (FanDuel) ──► odds_client.py ──► Game objects
                                                    │
SQLite team_stats DB ──────────────────────────────►│
                                                    ▼
                                           _select_markets()
                                       (1 spread + 1 total + 1 ML)
                                                    │
                                                    ▼
                                        ev_calculator.py (PydanticAI)
                                        5-step CoT reasoning per market
                                        Kelly Criterion unit sizing
                                                    │
                                                    ▼
                                           BetRecommendation
                                        (EV%, units, CoT steps)
                                                    │
                                         ┌──────────┴──────────┐
                                         ▼                      ▼
                                    SQLite DB              Streamlit UI
                                 (bets ledger)       (approve/reject/settle)
```

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Agent Framework | PydanticAI | Structured LLM output, retries |
| LLM | OpenAI GPT-4o-mini | Chain-of-thought reasoning |
| Odds Data | The-Odds-API v4 | Live FanDuel NCAAB lines |
| Structured Storage | SQLite + sqlite_utils | Bets, bankroll, team stats |
| Vector Store | LanceDB | Phase 2 RAG (news/injuries) |
| UI | Streamlit | Interactive dashboard |
| Language | Python 3.9+ | All components |

---

## Phase Roadmap

### ✅ Phase 1: Foundations (Weeks 1–4) — COMPLETE

**Goal:** Build the core EV analysis engine with structured output and persistent storage.

#### Week 1 — Project Setup & Data Models
- [x] Defined `BetType`, `BetSide`, `Odds`, `Game`, `TeamStats` Pydantic models
- [x] SQLite schema: `bets`, `bankroll`, `team_stats` tables
- [x] LanceDB table created for Phase 2 RAG (schema-only seed)
- [x] Pytest test suite (8 tests covering schemas, storage, Kelly)

#### Week 2 — EV Calculator Agent
- [x] PydanticAI agent with 5-step Chain-of-Thought system prompt
- [x] `EVAnalysis` structured output with `reasoning_steps`, `projected_win_probability`, `expected_value`
- [x] Quarter-Kelly Criterion unit sizing (hard-coded math, not LLM-estimated)
- [x] EV threshold: bets below +3.5% suppressed automatically
- [x] Unit floor: bets producing < 0.05u suppressed automatically

#### Week 3 — Structured Output & CLI
- [x] `BetRecommendation` with `is_recommended`, `summary`, `recommended_units`
- [x] `DailySlate` container with deduplication validator (prevents same-market contradiction)
- [x] CLI: `--slate`, `--bets`, `--pending`, `--approved`, `--bankroll`, `--settle`
- [x] `--approve` / `--reject` commands for human-in-the-loop

#### Week 4 — Knowledge Representation & Storage
- [x] 30-team stats seeded into SQLite from `data/team_stats.json`
- [x] `_lookup_team_stats()` with word-overlap fuzzy matching (prevents false P5 stat assignment)
- [x] No-data guard: skip LLM call if neither team has stats
- [x] `--seed` command to load/refresh team stats

---

### ✅ Phase 1.5: Live Data & Performance (Post-Week 4) — COMPLETE

**Goal:** Replace mock data with live APIs and make analysis production-grade.

- [x] **The-Odds-API integration** (`src/tools/odds_client.py`)
  - Live FanDuel spreads, totals, moneylines for all NCAAB games
  - Free tier: 500 req/month (~2 req per slate run)
  - Fallback to mock data if `ODDS_API_KEY` not set
- [x] **Moneyline bet support** — fetched, stored, analyzed (underdog side selected)
- [x] **Smart market selection** (`_select_markets`) — picks best-priced side per market
- [x] **Concurrent analysis** — all games × all markets via `asyncio.gather`
- [x] **Pre-LLM game ranking** — selects top N games by data richness + line pricing
- [x] **`--max-games` flag** — caps analysis to control API cost (default: 5)
- [x] **Streamlit dashboard** (`src/ui/app.py`)
  - Dark theme, live bankroll sidebar, Run Slate button
  - Bet cards with EV badges, CoT expander, Approve/Reject
  - Pending bets tab with settle form
  - History tab with P/L table
  - Game Search tab with chat-style odds lookup

---

### 🔜 Phase 2: RAG & Context Enrichment (Weeks 5–7)

**Goal:** Ground the agent's reasoning in real-world news, injury reports, and trend data.

#### Week 5 — News Ingestion Pipeline
- [ ] ESPN/AP news scraper or RSS feed ingestion
- [ ] Chunk articles by team name + date
- [ ] Embed with `sentence-transformers/all-MiniLM-L6-v2`
- [ ] Store in LanceDB `news_chunks` table

#### Week 6 — RAG-Enhanced Prompt
- [ ] `NewsVectorStore.search(team_name)` returns recent injury/form snippets
- [ ] Inject top-3 relevant chunks into `build_game_prompt` under "## News Context"
- [ ] Agent reasons over actual injury reports instead of "No news available"

#### Week 7 — GraphRAG: Team Similarity Network
- [ ] Build team graph: nodes = teams, edges = shared opponents (weighted by result)
- [ ] Use graph traversal to surface schedule-strength context
- [ ] "Team A beat Team B who beat Team C by 20" style reasoning

---

### 🔜 Phase 3: MCP & Multi-Agent (Weeks 8–11)

**Goal:** Expose the agent as a Model Context Protocol server and orchestrate a pipeline of specialist sub-agents.

#### Week 8–9 — MCP Server
- [ ] Wrap `get_live_games()` and `analyze_full_slate()` as MCP tools
- [ ] Expose `approve_bet`, `settle_bet` as MCP actions
- [ ] Clients: Claude Desktop, custom Streamlit MCP client

#### Week 10–11 — Multi-Agent Pipeline
- [ ] **Odds Watcher Agent** — monitors live line movement, flags sharp money
- [ ] **News Monitor Agent** — polls for injury news every 30 min, updates DB
- [ ] **Head Coach Agent** — orchestrates sub-agents, finalizes slate picks
- [ ] Human-in-the-loop: email/SMS digest of daily picks with approve links

---

### 🔜 Phase 4: Scale & Guardrails (Weeks 12–13)

**Goal:** Add reliability, logging, and anti-hallucination guards.

- [ ] No-vig fair-value calculator (remove sportsbook margin from implied prob)
- [ ] Line movement tracker: flag games where current line differs from open by > 2 pts
- [ ] Bet result tracking + auto-settlement via score API
- [ ] Confidence calibration: track projected vs. actual win % by bet type
- [ ] Rate-limit / cost guard: hard cap on LLM spend per day

---

### 🔜 Phase 5: Capstone Dashboard (Weeks 14–15)

**Goal:** Polish the Streamlit UI into a production-quality capstone demo.

- [ ] Real-time odds ticker (auto-refresh every 5 min)
- [ ] P/L chart by week / bet type / conference
- [ ] Best-performing model statistics (EV accuracy, ROI %)
- [ ] Export picks to CSV/PDF for course submission
- [ ] Deployed to Streamlit Cloud or Render for live demo

---

## Key Design Decisions

### Why Quarter-Kelly?
Full Kelly maximizes long-run log wealth but produces extreme variance. Quarter-Kelly (25% of the Kelly stake) is the industry standard for recreational and semi-professional bettors: it keeps drawdowns manageable while still scaling bets proportionally to edge.

### Why Analyze Only One Side Per Market?
The LLM evaluates each market independently without global probability context. Analyzing both Over and Under produces inconsistent probability estimates that can both appear +EV — a mathematical impossibility. Selecting only the better-priced side eliminates this and reduces LLM calls by 50%.

### Why Pre-Rank Games Before LLM Calls?
On a slate of 38 games, running 3 LLM calls per game would cost 114 calls and ~$0.15 per run. Pre-ranking by data richness (team stats availability) + line pricing (less juice) ensures the LLM's limited budget goes to the highest-quality analysis opportunities.

### Why SQLite Over a Cloud DB?
Phase 1 is designed for local development with a single user. SQLite is zero-configuration, file-based, and sufficient for the bet volumes this agent produces (< 100 bets/week). Phase 4 can migrate to PostgreSQL if multi-user access is needed.

---

## Running the Project

```bash
# Clone
git clone https://github.com/calreilly/Hoops-Edge.git
cd Hoops-Edge

# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # Add OPENAI_API_KEY and ODDS_API_KEY

# Seed team stats
python -m src.main --seed

# Launch dashboard (recommended)
streamlit run src/ui/app.py

# Or use CLI
python -m src.main --slate --max-games 5
python -m src.main --bets
python -m src.main --approve <bet-id-prefix>
python -m src.main --settle <bet-id-prefix> win 1.15
```

---

## File Structure

```
hoops-edge/
├── data/
│   ├── team_stats.json          # 30-team stats seed file
│   └── hoops_edge.db            # SQLite DB (bets, bankroll, team_stats)
├── src/
│   ├── agents/
│   │   └── ev_calculator.py     # PydanticAI EV agent + market selection
│   ├── db/
│   │   └── storage.py           # BetLedger (SQLite) + NewsVectorStore (LanceDB)
│   ├── models/
│   │   └── schemas.py           # Pydantic models: Game, BetRecommendation, DailySlate
│   ├── tools/
│   │   ├── odds_client.py       # The-Odds-API live odds fetcher
│   │   ├── kelly.py             # Quarter-Kelly Criterion calculator
│   │   ├── mock_odds.py         # Mock slate for testing without API key
│   │   └── seed_teams.py        # DB seeder for team_stats.json
│   ├── ui/
│   │   └── app.py               # Streamlit dashboard
│   └── main.py                  # CLI entrypoint
├── tests/
│   └── test_phase1.py           # 8-test pytest suite
├── .env.example                 # Template for API keys
├── requirements.txt
├── README.md
└── PROJECT_SPEC.md              # This file
```
