# Hoops Edge

A CBB +EV betting agent for GRAD5900. Analyzes college basketball games and identifies positive expected value bets on FanDuel.

## Phase 1 Features
- PydanticAI EV Calculator with Chain-of-Thought reasoning
- Structured `BetRecommendation` output (typed bet, stake, EV, confidence)
- SQLite ledger for bets and bankroll tracking
- LanceDB for future news/injury RAG (Phase 2)

## Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Add your OpenAI key
```

## Run
```bash
# Analyze today's mock slate
python -m src.main --slate

# Show pending bets in DB
python -m src.main --bets

# Check bankroll
python -m src.main --bankroll
```

## Project Roadmap
See [`PROJECT_SPEC.md`](./PROJECT_SPEC.md) for full 15-week roadmap.

## Tech Stack
- **Agent**: PydanticAI + OpenAI
- **DB**: SQLite (bets/bankroll) + LanceDB (vectors)
- **Odds**: Mock data (Phase 1) → The-Odds-API MCP Server (Phase 3)
