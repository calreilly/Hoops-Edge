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

LIVE_SYSTEM_PROMPT = """
You are Hoops Edge, an elite quantitative sports betting analyst providing real-time game tracking.
Your task is to analyze an in-progress or recently completed college basketball game in the context of an open bet.

INSTRUCTIONS:
1. You will receive the original pre-game bet rationale, the bet market/side, and the current live game score/box score.
2. Assess whether the bet thesis is currently playing out — is the bet on track to win, in trouble, or too early to tell?
3. Identify 2-3 key in-game factors (scoring runs, efficiency, turnovers, shooting %) driving the current score.
4. Give a confidence update: is the original rationale still valid given what you see?
5. Be concise (3-4 sentences). Use specific stats from the box score where possible.
"""

model = OpenAIModel(model_name=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

post_mortem_agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    output_type=str,
    retries=1,
)

live_analysis_agent = Agent(
    model=model,
    system_prompt=LIVE_SYSTEM_PROMPT,
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


async def generate_live_analysis(
    matchup: str,
    market: str,
    rationale: str,
    live_context: str,
) -> str:
    """
    Run an LLM call to assess an in-progress or recently completed game
    against the original bet thesis.
    """
    prompt = f"""
## Bet Information
Matchup: {matchup}
Market: {market}

## Original Pre-Game Rationale
{rationale}

## Current Live Game Context
{live_context}

Provide a 3-4 sentence live game analysis: is the bet currently on track, what key factors are driving the score, and is the original thesis still valid?
"""
    response = await live_analysis_agent.run(prompt)
    return response.output
