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

Open **Today's Slate** from the sidebar. Click **Load Today's Games** to pull live FanDuel odds for every game on the day's NCAAB slate. Check the checkbox beneath any game card you want to analyze — the top bar updates to show how many you have selected, and the **▶ Analyze** and **🪄 AI Previews** buttons activate.

![Step 1 – Two games selected from the slate: Iowa State vs Arizona and Duke vs NC State. The control bar shows "Selected 2 for analysis."](docs/screenshots/step1_select_games.png)

> **Tip:** Use the sidebar filters (conference, spread size, win threshold) to narrow a slate of 30+ games down to the highest-quality matchups before selecting.

---

#### Step 2 — Generate AI Previews

With games selected, click **🪄 AI Previews (N)**. The agent reads the matchup data and generates a concise edge summary for each game — surfacing pace mismatches, 3PT reliance, ATS trends, and defensive vulnerabilities — displayed in purple directly on the game card. Use this as a quick sanity check before committing API credits to a full analysis.

![Step 2 – AI Edge previews appear on both game cards. For Iowa State vs Arizona, the agent flags Iowa State's slower pace facing Arizona's transition offense and notes the importance of limiting 3PT opportunities.](docs/screenshots/step2_ai_previews.png)

> **Tip:** Previews are fast and cheap. Full EV analysis (next step) runs the complete 5-step Chain-of-Thought reasoning and costs more OpenAI tokens.

---

#### Step 3 — Run Full EV Analysis & Review Picks

Click **▶ Analyze N Games** to run the complete Chain-of-Thought EV analysis. The agent evaluates each market (spread, total, moneyline), calculates the true no-vig implied probability, applies quarter-Kelly unit sizing, and surfaces only bets that clear the +3.5% EV threshold. Results appear automatically on the **Picks & Analysis** page.

Expand the **🧠 Reasoning** section on any bet card to read the agent's full 5-step justification — including efficiency metrics, recent form, defensive vulnerabilities, historical ROI, and the final win probability estimate.

![Step 3 – Duke Blue Devils @ NC State: SPREAD HOME +11.5 flagged at +4.6% EV with 74% confidence. The 5-step Chain-of-Thought reasoning is expanded, citing Duke's defensive efficiency, NC State's recent losses to Virginia and Notre Dame, and a projected 70% win probability.](docs/screenshots/step3_analysis_results.png)

> **Tip:** Click **📌 Place Bet** to move the bet to your pending ledger, or **✖ Skip** to dismiss it. Placed bets are tracked against your bankroll and settled from the **Pending Bets** page.

---

### 🏟️ Teams Explorer — Research Any Division I Program

#### Step 4 — Search for a Team

Open **Teams** from the sidebar. Type any team name into the search box to instantly filter the full grid of 362 Division I programs. The grid supports search by nickname, city, or official name across Men's College Basketball, Women's College, and NBA. Click **View** on any card to open the full team profile.

![Step 4 – Typing "UConn" into the search box instantly filters the grid to the UConn Huskies card.](docs/screenshots/step4_teams_search.png)

---

#### Step 5 — Explore the Full Team Profile

The team profile modal displays a live-updated header showing the overall record, home/road splits, AP ranking badge, conference standing, and a scrollable ribbon of recent game results. Three tabs organize the data:

- **📋 Roster** — Full player grid with headshots, position, height, year, and expandable Stats & Scouting sections for each player
- **📅 Schedule** — Full season schedule pulled from ESPN with results, opponents, and game-by-game outcomes for spotting hot/cold streaks
- **🧠 Facts** — AI Scouting Overview (GPT-4o-mini) covering offensive/defensive tendencies, key players, pace, 3PT rate, and situational strengths — cached for instant repeat loads

![Step 5 – UConn Huskies team profile: 27-3 overall · 15-2 home · 9-1 road · #4 AP · 1st in Big East. The Roster tab shows the full player grid with headshots for Solo Ball, Silas Demary Jr., Brezon Eleraji, and more.](docs/screenshots/step5_uconn_profile.png)

> **Tip:** Use the **Schedule** tab to spot momentum shifts before a game — a team on a 5-game win streak vs. a team that just lost three straight is context the betting lines may not fully price in.

