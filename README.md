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

---

## 📖 Usage Tutorial

### 🏀 Today's Slate — Select, Preview & Analyze Games

#### Step 1 — Load Games and Select Matchups

Open **Today's Slate** from the sidebar. Click **Load Today's Games** to pull live FanDuel odds. Check the checkbox beneath any game card you want to analyze — the top bar updates to show how many you have selected.

![Step 1 – Select games from the slate](docs/screenshots/step1_select_games.png)

> **Tip:** Use the filters in the sidebar (conference, spread size, win threshold) to narrow down the slate before selecting.

---

#### Step 2 — Generate AI Previews

With games selected, click **🪄 AI Previews (N)** at the top. The agent generates a concise edge summary for each selected game — highlighting key matchup factors, pace mismatches, or line inefficiencies — displayed directly on the game card in purple.

![Step 2 – AI-generated edge previews appear on each selected game card](docs/screenshots/step2_ai_previews.png)

> **Tip:** Use previews as a quick gut-check before committing to a full EV analysis run, which uses more API credits.

---

#### Step 3 — Run Full EV Analysis

Click **▶ Analyze N Games** to run the full Chain-of-Thought EV analysis. The agent evaluates each market (spread, total, moneyline), calculates true implied probability, applies quarter-Kelly sizing, and surfaces only bets above the +3.5% EV threshold. Results appear automatically on the **Picks & Analysis** page.

![Step 3 – Bet recommendations with EV scores and Chain-of-Thought reasoning](docs/screenshots/step3_analysis_results.png)

> **Tip:** Expand the **🧠 Reasoning** section on any bet card to read the agent's full Chain-of-Thought justification before approving.

---

### 🏟️ Teams Explorer — Research Any Division I Program

#### Step 4 — Search for a Team

Open **Teams** from the sidebar. Type any team name into the search box to filter the grid of all 362 Division I programs instantly. Click **View Profile** on any card to open the full team profile.

![Step 4 – Searching for "UConn" in the Teams Explorer](docs/screenshots/step4_teams_search.png)

---

#### Step 5 — View the Season Schedule

On the team profile page, click the **📅 Schedule** tab. This pulls the full current-season schedule from ESPN, showing results, opponents, and game-by-game outcomes — useful for spotting hot/cold streaks heading into a matchup.

![Step 5 – UConn Huskies season schedule with results](docs/screenshots/step5_uconn_schedule.png)

---

#### Step 6 — Read the AI Scouting Overview

Click the **🧠 Facts** tab. Hoops Edge generates a structured scouting report powered by GPT-4o-mini, covering offensive and defensive tendencies, key players, recent form, and situational strengths. The overview is cached so it loads instantly on repeat visits.

![Step 6 – AI-generated scouting overview for UConn Huskies](docs/screenshots/step6_uconn_facts.png)

> **Tip:** The **Facts** tab also shows adjusted efficiency metrics (AdjO / AdjD), pace rating, 3PT rate, and the team's best wins and worst losses from the current season.

