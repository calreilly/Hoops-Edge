"""
Qualitative Evaluation Suite for Hoops Edge AI Agents.

Uses an LLM-as-a-judge to evaluate the factual accuracy, reasoning, 
and predictive value of AI-generated scouting reports by comparing 
them against the actual settled game box scores and outcomes.
"""

import sys
import asyncio
from pathlib import Path
from pydantic_ai import Agent

# Add project root to sys.path so we can import src modules
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.db.storage import BetLedger
from src.agents.post_mortem import model

# Define the judge agent
JUDGE_SYSTEM_PROMPT = """
You are an expert AI evaluator and college basketball analyst.
Your task is to grade an AI-generated pre-game scouting report against what actually happened in the game.

You will be provided with:
1. The AI's Pre-Game Scouting Report
2. The Actual Game Outcome (Score & High-level stats if available)

Please evaluate the scouting report on the following criteria on a scale of 1 to 5:
- Factual Accuracy (Did the report correctly identify team strengths based on season stats?)
- Predictive Value (Did the "Key Matchup Factors" end up mattering in the actual game outcome?)
- Alignment with Reality (If the report predicted a fast-paced shootout, did it happen?)

Provide a short 2-3 sentence justification, and then a final score out of 5 using the exact format:
FINAL SCORE: X/5
"""

judge_agent = Agent(
    model=model,
    system_prompt=JUDGE_SYSTEM_PROMPT,
    output_type=str,
    retries=1
)

async def evaluate_scouting_report(away_team: str, home_team: str, report_text: str, outcome_context: str) -> str:
    prompt = f"""
## Matchup
{away_team} @ {home_team}

## AI Pre-Game Scouting Report
{report_text}

## Actual Game Outcome
{outcome_context}

Please evaluate the scouting report.
"""
    result = await judge_agent.run(prompt)
    return result.output

async def run_ai_evals():
    ledger = BetLedger()
    
    # Get recent settled bets and their summaries (rationale)
    # Since we don't have stored pre-game scouting reports in the DB (only in cache for live games),
    # we will evaluate the `summary` column of the bets table, which represents the AI's preview analysis.
    
    settled_bets = list(ledger.db["bets"].rows_where("status = 'settled' limit 3"))
    
    if not settled_bets:
        print("No settled bets found in DB to evaluate.")
        return
        
    print(f"Evaluating {len(settled_bets)} AI Previews against actual outcomes using LLM-as-a-judge...\n")
    
    for bet in settled_bets:
        home = bet["home_team"]
        away = bet["away_team"]
        ai_rationale = bet.get("summary", "No rationale found.")
        
        # Determine actual outcome based on bet result and side
        result_status = bet["result"] # "win" or "loss"
        side = bet["side"].upper()
        
        outcome_desc = f"The user bet {side} and the result was a {result_status.upper()}."
        
        print(f"==================================================")
        print(f"🎲 Matchup: {away} @ {home}")
        print(f"🤖 AI Preview/Rationale: {ai_rationale}")
        print(f"📈 Actual Outcome Context: {outcome_desc}")
        print(f"--- ⚖️ JUDGE EVALUATION ---")
        
        eval_text = await evaluate_scouting_report(away, home, ai_rationale, outcome_desc)
        print(eval_text)
        print(f"==================================================\n")


if __name__ == "__main__":
    asyncio.run(run_ai_evals())
