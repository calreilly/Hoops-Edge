import os
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """
You are Hoops Edge, an elite quantitative sports betting analyst.
Your task is to provide a "Post-Mortem" grading for a settled college basketball bet.

INSTRUCTIONS:
1. You will receive the original pre-game bet rationale, the bet type/side, and the final recorded box score or game result from ESPN.
2. Cross-reference the pre-game rationale against what actually happened in the game.
3. Provide a concise, 3-sentence explanation of why the bet won or lost. Did the team underperform their offensive efficiency? Was the pace too slow for the over? Identify the core reason.
4. Be objective. If the initial rationale was wrong, say so.
"""

model = OpenAIModel(model_name=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

post_mortem_agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    output_type=str,
    retries=1,
)

async def generate_post_mortem(
    matchup: str,
    market: str,
    rationale: str,
    result: str,
    final_score_context: str
) -> str:
    """
    Run an LLM call to explain why a bet won or lost based on the final box score.
    """
    prompt = f"""
## Bet Information
Matchup: {matchup}
Market: {market}
Result: {result.upper()}

## Pre-Game Rationale
{rationale}

## Final Game Context
{final_score_context}

Write a 3-sentence retroactive post-mortem explaining why this bet succeeded or failed.
"""
    response = await post_mortem_agent.run(prompt)
    return response.output
