"""
March Madness Bracket Simulator.
Takes a list of 64 teams (arranged in bracket order) and simulates the tournament
round-by-round using the `math_model` projection engine.
"""

import sys
import json
from pathlib import Path

# Add project root to sys.path so we can import src modules
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.db.storage import BetLedger
from src.tools.math_model import project_matchup

def get_stats_map() -> dict:
    """Load all team stats from the database into a dictionary keyed by team name."""
    ledger = BetLedger()
    stats = ledger.get_all_team_stats()
    return {t["team_name"]: t for t in stats}

def simulate_game(team1: str, team2: str, stats_map: dict) -> tuple[str, str, float]:
    """
    Simulate a game between two teams using the math model.
    Returns (winner_name, loser_name, home_win_probability).
    Treats team1 as the "Away" team and team2 as the "Home" team in the model,
    but always forces neutral site.
    """
    t1_stats = stats_map.get(team1, {})
    t2_stats = stats_map.get(team2, {})
    
    # If missing stats, just pass empty dicts (math_model uses NCAA averages)
    # The math model defines project_matchup(away, home)
    # the returned projected_margin > 0 means 'home' (team2) wins.
    res = project_matchup(t1_stats, t2_stats, is_neutral_site=True)
    
    if res["projected_margin"] > 0:
        return team2, team1, res["home_win_prob"]
    else:
        return team1, team2, res["away_win_prob"]

def run_tournament(bracket_teams: list[str]) -> None:
    """
    Given an ordered list of 64 teams representing a bracket layout,
    simulate the entire tournament and print a markdown report.
    """
    if len(bracket_teams) not in [4, 8, 16, 32, 64]:
        print(f"Error: Bracket must have exactly 4, 8, 16, 32, or 64 teams. Found {len(bracket_teams)}.")
        return

    stats_map = get_stats_map()
    
    rounds = []
    current_round = bracket_teams
    
    # Round names based on remaining teams
    round_names = {
        64: "Round of 64", 32: "Round of 32", 16: "Sweet 16", 
        8: "Elite 8", 4: "Final Four", 2: "National Championship"
    }

    print("# 🏆 March Madness Bracket Simulation\n")
    
    while len(current_round) > 1:
        next_round = []
        round_name = round_names.get(len(current_round), f"Round of {len(current_round)}")
        print(f"## {round_name}")
        
        # Play pairs
        for i in range(0, len(current_round), 2):
            team1 = current_round[i]
            team2 = current_round[i+1]
            
            winner, loser, win_prob = simulate_game(team1, team2, stats_map)
            next_round.append(winner)
            
            # Print matchup result
            prob_pct = win_prob * 100
            print(f"- **{winner}** ({prob_pct:.1f}%) defeats {loser}")
            
        print("\n")
        current_round = next_round
        
    print(f"## 🏆 National Champion: **{current_round[0]}** 🎉")

if __name__ == "__main__":
    # Test layout with 64 random teams from the database if no file provided
    stats_map = get_stats_map()
    all_teams = list(stats_map.keys())
    
    # Determine the largest bracket we can run
    for size in [64, 32, 16, 8, 4]:
        if len(all_teams) >= size:
            bracket_size = size
            break
    else:
        print(f"Not enough teams in database to run even a 4-team bracket (Found {len(all_teams)}).")
        sys.exit(1)
        
    print(f"Loaded {len(all_teams)} teams from database. Running a mock {bracket_size}-team tournament...")
    
    # Let's grab the top 'bracket_size' teams by raw efficiency margin (AdjO - AdjD) to make it semi-realistic
    def eff_margin(name):
        st = stats_map[name]
        try:
            return float(st.get("adj_o", 100)) - float(st.get("adj_d", 100))
        except:
            return 0
            
    best_teams = sorted(all_teams, key=eff_margin, reverse=True)[:bracket_size]
    
    # Shuffle slightly so 1 doesn't always play 2 early
    import random
    random.seed(42) # Deterministic for testing
    random.shuffle(best_teams)
    
    run_tournament(best_teams)
