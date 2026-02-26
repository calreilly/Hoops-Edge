import os
import json
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from dotenv import load_dotenv

from src.models.schemas import Game

load_dotenv()

SYSTEM_PROMPT = """
You are Hoops Edge, an elite quantitative sports betting analyst. 
Your task is to provide a rapid-fire "What to Watch For" preview for a list of college basketball games.

INSTRUCTIONS:
1. You will receive a JSON list of games containing team names, efficiency stats, pace, and current odds.
2. For each game, write exactly TWO sentences summarizing the key stylistic clashes or edges (e.g., pace vs. half-court, elite defense vs. high-powered offense, heavy favorite vs. scrappy underdog).
3. Do not just restate the odds. Focus on how the teams match up on the court based on the provided stats.
4. Output a simple JSON dictionary mapping the exact `game_id` to the 2-sentence preview string.
"""

model = OpenAIModel(model_name=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

preview_agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    output_type=str,
    retries=1,
)

async def generate_slate_previews(games: list[Game]) -> dict[str, str]:
    """
    Run a single batch LLM call to preview the given games.
    Returns: {game_id: "2 sentence preview text"}
    """
    if not games:
        return {}

    # Condense payload to save tokens
    condensed = []
    for g in games:
        condensed.append({
            "game_id": g.game_id,
            "matchup": f"{g.away_team} @ {g.home_team}",
            "away_stats": {
                "oe": g.away_stats.offensive_efficiency if g.away_stats else None,
                "de": g.away_stats.defensive_efficiency if g.away_stats else None,
                "pace": g.away_stats.pace if g.away_stats else None,
                "3pr": g.away_stats.three_point_rate if g.away_stats else None,
            } if g.away_stats else None,
            "home_stats": {
                "oe": g.home_stats.offensive_efficiency if g.home_stats else None,
                "de": g.home_stats.defensive_efficiency if g.home_stats else None,
                "pace": g.home_stats.pace if g.home_stats else None,
                "3pr": g.home_stats.three_point_rate if g.home_stats else None,
            } if g.home_stats else None,
            "spread": f"{g.home_team} {g.home_odds.line:+.1f}" if g.home_odds and g.home_odds.line else "N/A",
            "total": g.total_over_odds.line if g.total_over_odds and g.total_over_odds.line else "N/A",
        })

    prompt = f"Analyze these {len(games)} games:\n{json.dumps(condensed, indent=2)}"
    
    try:
        result = await preview_agent.run(prompt)
        text = result.output.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
            
        return json.loads(text.strip())
    except Exception as e:
        print(f"Error generating slate previews: {e}")
        return {}

