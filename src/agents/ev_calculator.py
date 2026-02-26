"""
Phase 1 - Week 2 & 3: EV Calculator Agent
Uses Chain-of-Thought (CoT) prompting via PydanticAI to:
  1. Reason through team stats and matchup context
  2. Estimate a win probability
  3. Compare it against the sportsbook implied probability
  4. Output a structured BetRecommendation
"""
import os
import asyncio
from datetime import datetime
from typing import Optional
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from dotenv import load_dotenv

from src.models.schemas import (
    Game, EVAnalysis, BetRecommendation, BetType, BetSide, DailySlate
)

load_dotenv()

# --- System Prompt (Week 2: Reasoning as Logic) ---
SYSTEM_PROMPT = """
You are Hoops Edge, an elite quantitative sports betting analyst specializing 
in NCAA college basketball (+EV identification).

Your job is to analyze a college basketball game and identify whether any betting 
market offers POSITIVE EXPECTED VALUE (+EV) on FanDuel.

## Reasoning Protocol (Chain-of-Thought)
You MUST reason step-by-step. For each market (spread, moneyline, total) you evaluate:

STEP 1 — Team Context: Summarize each team's offensive/defensive efficiency, pace, 
         recent form, and relevant injuries.
STEP 2 — Matchup Analysis: Identify key stylistic advantages (e.g., "Team A's 
         elite 3-point defense smothers Team B's pace-and-space offense").
STEP 3 — Probability Estimation: State your estimated win probability for each 
         side, with explicit justification.
STEP 4 — EV Calculation: EV = (your_prob * decimal_odds) - 1
         If EV > 0.03 (3%) → flag as a potential bet.
STEP 5 — Confidence Check: Rate your confidence (0.0–1.0). If confidence < 0.55, 
         reduce unit size. Never recommend a bet with confidence < 0.50.

## Unit Sizing (Kelly Criterion, quarter-Kelly)
units = (edge / (decimal_odds - 1)) * 0.25
Cap maximum units at 3.0 per bet. Never recommend a parlay of more than 3 legs.

## Output Rules
You MUST return a valid JSON object matching BetRecommendation exactly:
- game_id: string (copy from input)
- home_team / away_team: strings (copy from input)
- game_time: ISO 8601 datetime string
- bet_type: one of "spread", "moneyline", "total", "player_prop"
- side: one of "home", "away", "over", "under"
- line: float or null
- american_odds: integer
- ev_analysis object with:
    - bet_type / side: same as above
    - reasoning_steps: list of 3-5 strings (your CoT steps)
    - projected_win_probability: float 0.0-1.0
    - implied_probability: float 0.0-1.0 (compute from odds)
    - expected_value: float (= projected_prob * decimal_odds - 1)
    - confidence: float 0.0-1.0
- recommended_units: float 0.0-3.0
- is_recommended: boolean (true only if EV > 0.03 AND confidence >= 0.55)
- summary: string, max 25 words
"""

# Initialize agent with structured output type
model = OpenAIModel(
    model_name=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
)

ev_agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    output_type=BetRecommendation,
    retries=3,
)


def build_game_prompt(game: Game, bet_type: BetType, side: BetSide) -> str:
    """Build the user message for the agent to analyze a specific market."""
    
    # Get relevant odds
    odds = None
    if bet_type == BetType.SPREAD and side == BetSide.HOME:
        odds = game.home_odds
    elif bet_type == BetType.SPREAD and side == BetSide.AWAY:
        odds = game.away_odds
    elif bet_type == BetType.TOTAL and side == BetSide.OVER:
        odds = game.total_over_odds
    elif bet_type == BetType.TOTAL and side == BetSide.UNDER:
        odds = game.total_under_odds
    elif bet_type == BetType.MONEYLINE and side == BetSide.HOME:
        odds = game.home_ml
    elif bet_type == BetType.MONEYLINE and side == BetSide.AWAY:
        odds = game.away_ml

    if odds is None:
        raise ValueError(f"No odds found for {bet_type} / {side}")

    # Build home stats block
    home_block = "No stats available."
    if game.home_stats:
        s = game.home_stats
        home_block = (
            f"Record: {s.record} | Off Eff: {s.offensive_efficiency} | "
            f"Def Eff: {s.defensive_efficiency} | Pace: {s.pace} | "
            f"3PT Rate: {s.three_point_rate} | ATS: {s.ats_record}"
        )

    away_block = "No stats available."
    if game.away_stats:
        s = game.away_stats
        away_block = (
            f"Record: {s.record} | Off Eff: {s.offensive_efficiency} | "
            f"Def Eff: {s.defensive_efficiency} | Pace: {s.pace} | "
            f"3PT Rate: {s.three_point_rate} | ATS: {s.ats_record}"
        )

    # Full odds context so agent can reason about the market structure
    spread_ctx = ""
    if game.home_odds and game.away_odds:
        spread_ctx = (f"Spread: {game.home_team} {game.home_odds.line:+.1f} "
                      f"({'%+d' % game.home_odds.american_odds}) / "
                      f"{game.away_team} {game.away_odds.line:+.1f} "
                      f"({'%+d' % game.away_odds.american_odds})")

    total_ctx = ""
    if game.total_over_odds and game.total_under_odds:
        total_ctx = (f"Total: O/U {game.total_over_odds.line} "
                     f"(O {'%+d' % game.total_over_odds.american_odds} / "
                     f"U {'%+d' % game.total_under_odds.american_odds})")

    ml_ctx = ""
    if game.home_ml and game.away_ml:
        ml_ctx = (f"Moneyline: {game.home_team} {'%+d' % game.home_ml.american_odds} / "
                  f"{game.away_team} {'%+d' % game.away_ml.american_odds}")

    return f"""
## Game: {game.away_team} @ {game.home_team}
Game Time: {game.game_time.strftime('%A %b %d, %Y %I:%M %p')}
Game ID: {game.game_id}

## Market to Evaluate
Type: {bet_type.value.upper()}
Side: {side.value.upper()}
Line: {odds.line if odds.line else 'N/A'}
American Odds (FanDuel): {odds.american_odds}
Implied Probability: {odds.implied_probability:.1%}

## All Available Lines (FanDuel context)
{spread_ctx}
{total_ctx}
{ml_ctx}

## Team Stats
{game.home_team} (HOME):
{home_block}

{game.away_team} (AWAY):
{away_block}

## Injury / News Context
{game.injury_notes or 'No significant injury news available.'}

---
Analyze this market. Follow the 5-step reasoning protocol.
Output a BetRecommendation.
"""


from src.tools.kelly import apply_kelly_to_recommendation


async def analyze_game_market(
    game: Game,
    bet_type: BetType,
    side: BetSide,
) -> BetRecommendation:
    """
    Run the EV agent for one specific market of a game.
    Returns a BetRecommendation with embedded CoT reasoning.
    The recommended_units field is post-processed with hard Kelly math.

    Guard: if neither team has stats, skip LLM and return a no-confidence placeholder
    rather than letting the agent hallucinate stats.
    """
    if game.home_stats is None and game.away_stats is None:
        raise ValueError("No stats available for either team — skipping LLM call")

    prompt = build_game_prompt(game, bet_type, side)
    result = await ev_agent.run(prompt)
    rec = result.output

    # ENFORCE the requested parameters to prevent LLM hallucinations
    # from accidentally colliding unique bets in the DailySlate validator.
    rec.game_id = game.game_id
    rec.bet_type = bet_type
    rec.side = side

    # Override agent's unit suggestion with hard quarter-Kelly math (Week 2 improvement)
    apply_kelly_to_recommendation(rec)

    return rec


def _select_markets(game: Game) -> list[tuple[BetType, BetSide]]:
    """
    Select ONE side per market to analyze — the side with better American odds
    (less juice = more value). This prevents the LLM from analyzing both sides
    independently and producing contradictory probability estimates.

    Logic:
      - Spread: pick whichever side (home or away) has the higher American odds
      - Total: pick whichever side (over or under) has the higher American odds
    """
    markets = []

    # Spread: pick the less-juiced side
    if game.home_odds and game.away_odds:
        if game.away_odds.american_odds >= game.home_odds.american_odds:
            markets.append((BetType.SPREAD, BetSide.AWAY))
        else:
            markets.append((BetType.SPREAD, BetSide.HOME))
    elif game.home_odds:
        markets.append((BetType.SPREAD, BetSide.HOME))
    elif game.away_odds:
        markets.append((BetType.SPREAD, BetSide.AWAY))

    # Total: pick the less-juiced side
    if game.total_over_odds and game.total_under_odds:
        if game.total_under_odds.american_odds >= game.total_over_odds.american_odds:
            markets.append((BetType.TOTAL, BetSide.UNDER))
        else:
            markets.append((BetType.TOTAL, BetSide.OVER))
    elif game.total_over_odds:
        markets.append((BetType.TOTAL, BetSide.OVER))
    elif game.total_under_odds:
        markets.append((BetType.TOTAL, BetSide.UNDER))

    # Moneyline: pick the underdog (higher American odds = more value potential)
    # Favorites at -300 rarely have EV; underdogs at +150 might
    if game.home_ml and game.away_ml:
        if game.away_ml.american_odds >= game.home_ml.american_odds:
            markets.append((BetType.MONEYLINE, BetSide.AWAY))
        else:
            markets.append((BetType.MONEYLINE, BetSide.HOME))
    elif game.home_ml:
        markets.append((BetType.MONEYLINE, BetSide.HOME))
    elif game.away_ml:
        markets.append((BetType.MONEYLINE, BetSide.AWAY))

    return markets


async def _analyze_game_all_markets(
    game: Game,
) -> list[BetRecommendation]:
    """Analyze the best side of each market for a game concurrently."""
    markets = _select_markets(game)

    async def safe_analyze(bet_type: BetType, side: BetSide):
        try:
            return await analyze_game_market(game, bet_type, side)
        except Exception as e:
            print(f"  [Warning] Skipped {game.away_team} @ {game.home_team} "
                  f"{bet_type.value}/{side.value}: {e}")
            return None

    results = await asyncio.gather(*[safe_analyze(bt, s) for bt, s in markets])
    return [r for r in results if r is not None]



async def analyze_full_slate(games: list[Game], max_games: int = 5) -> DailySlate:
    """
    Fully concurrent analysis: all games AND all markets run in parallel.
    Games are pre-ranked by quality before LLM calls:
      1. Data richness — prefer games where we have stats for both teams
      2. Line pricing  — prefer less juice (higher american_odds = user-friendlier)
    max_games caps slate size to control API cost (default: 5 games).
    """
    from datetime import date

    def _rank_score(game: Game) -> tuple:
        """Higher = better game to analyze. Returns tuple for lexicographic sort."""
        # (1) How much team context do we have?
        stats_score = (1 if game.home_stats else 0) + (1 if game.away_stats else 0)

        # (2) How good is the pricing on the markets we'll analyze?
        markets = _select_markets(game)
        pricing_score = 0
        for bt, side in markets:
            if bt == BetType.SPREAD:
                odds_obj = game.away_odds if side == BetSide.AWAY else game.home_odds
            elif side == BetSide.OVER:
                odds_obj = game.total_over_odds
            else:
                odds_obj = game.total_under_odds
            if odds_obj:
                pricing_score += odds_obj.american_odds  # -102 > -115 → better price

        return (stats_score, pricing_score)

    # Rank all games before capping; this selects the most promising N games
    ranked = sorted(games, key=_rank_score, reverse=True)[:max_games]
    print(f"  Ranked {len(games)} games → analyzing top {len(ranked)}...\n")
    games = ranked

    # Run ALL game-market combos concurrently
    async def analyze_one(game: Game, bet_type: BetType, side: BetSide):
        try:
            rec = await analyze_game_market(game, bet_type, side)
            return rec
        except Exception as e:
            print(f"  [Warning] Skipped {game.away_team} @ {game.home_team} "
                  f"{bet_type.value}/{side.value}: {e}")
            return None

    tasks = [
        analyze_one(game, bt, s)
        for game in games
        for bt, s in _select_markets(game)   # 1 spread + 1 total per game only
    ]

    results = await asyncio.gather(*tasks)
    all_recs = [r for r in results if r is not None]

    # Print per-game summary
    for game in games:
        game_recs = [r for r in all_recs if r.game_id == game.game_id]
        ev_bets = [r for r in game_recs if r.is_recommended]
        status = f"✅ {len(ev_bets)} +EV" if ev_bets else "❌ no edge"
        print(f"  {game.away_team} @ {game.home_team}: {status}")

    total_units = sum(r.recommended_units for r in all_recs if r.is_recommended)

    return DailySlate(
        date=datetime.now().strftime("%Y-%m-%d"),  # local date, not UTC
        games_analyzed=len(games),
        bets=all_recs,
        total_units_at_risk=total_units,
    )


