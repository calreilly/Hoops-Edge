# Hoops Edge

A college basketball +EV betting agent built for GRAD5900. Analyzes live FanDuel NCAAB lines and identifies positive expected value bets using an AI reasoning agent.

## How It Works

1. **Fetches live FanDuel NCAAB odds** from The-Odds-API (real spreads, totals, moneylines)
2. **Selects the better-odds side** of each market (avoids analyzing both sides of the same bet)
3. **Runs a PydanticAI reasoning agent** using 5-step Chain-of-Thought prompting to estimate win probability
4. **Calculates EV** = `(projected_prob × decimal_odds) − 1`
5. **Applies quarter-Kelly sizing** in code (overrides the LLM's unit suggestion with hard math)
6. **Saves approved bets** to SQLite and tracks bankroll

## Setup

```bash
# 1. Create virtual environment
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Set API keys
cp .env.example .env
# Edit .env: add OPENAI_API_KEY and ODDS_API_KEY

# 3. Seed team stats into DB (one-time)
python -m src.main --seed
```

Get a free Odds API key at [the-odds-api.com](https://the-odds-api.com) (500 req/month free).

## Usage

Hoops Edge now features a full browser-based dashboard. To launch the application:

```bash
# Start the Streamlit server
streamlit run src/ui/app.py
```

This will automatically open the UI in your browser at `http://localhost:8501`.

### Dashboard Features
* **Today's Slate:** Load live FanDuel odds and select games for the AI to analyze.
* **Picks & Analysis:** Review the expected value (EV) calculations and the AI's Chain-of-Thought reasoning for every bet recommendation.
* **Teams Explorer:** Deep-dive into any of the 362 Division 1 programs to view Live AP rankings, Rosters, Schedules, and comprehensive Scouting Reports.
* **Pending Bets:** Track open positions and settle them once the games have concluded.
* **Performance:** Monitor your all-time profit/loss, win/loss record, and adjust your starting Bankroll units and dollar-valuation configurations.

## Tech Stack

| Layer | Technology |
|---|---|
| Agent | PydanticAI + OpenAI (gpt-4o-mini) |
| Odds | The-Odds-API (live FanDuel lines) |
| Reasoning | 5-step Chain-of-Thought prompt |
| Unit sizing | Quarter-Kelly Criterion (code, not LLM) |
| Storage | SQLite (bets/bankroll/team stats) |
| Vectors | LanceDB (Phase 2 RAG) |

## Project Roadmap

| Phase | Weeks | Status |
|---|---|---|
| Phase 1: Foundations | 1–4 | ✅ Complete |
| Phase 2: RAG & Graph | 5–7 | 🔜 Next |
| Phase 3: MCP & Agents | 8–11 | 🔜 Planned |
| Phase 4: Scale & Guardrails | 12–13 | 🔜 Planned |
| Phase 5: Capstone Dashboard | 14–15 | 🔜 Planned |

See [`PROJECT_SPEC.md`](./PROJECT_SPEC.md) for the full 15-week breakdown.
