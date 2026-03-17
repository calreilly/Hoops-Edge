"""
Quantitative Evaluation Suite for Hoops Edge Math Model.

Backtests project_matchup() against historical settled bets in the database
to measure expected win probabilities against actual outcomes.
"""

import sys
from pathlib import Path

# Add project root to sys.path so we can import src modules
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.db.storage import BetLedger
from src.tools.math_model import project_matchup

def run_backtest():
    ledger = BetLedger()
    
    # Get all settled games
    # In Hoops Edge, a "bet" has standard game info. We will use settled bets as our ground-truth games.
    settled_bets = list(ledger.db["bets"].rows_where("status = 'settled'"))
    
    if not settled_bets:
        print("No settled bets found in DB to run evaluation against.")
        return
        
    print(f"Loaded {len(settled_bets)} settled bets for evaluation.\n")
    
    # Load stats map
    stats_map = {t["team_name"]: t for t in ledger.get_all_team_stats()}
    
    total_games = 0
    correct_predictions = 0
    brier_score_sum = 0.0
    
    # Bins for calibration curve: (0.5-0.6), (0.6-0.7), etc.
    # Stored as dict of {bin_start: {"count": 0, "wins": 0}}
    calibration_bins = {
        0.5: {"count": 0, "wins": 0},
        0.6: {"count": 0, "wins": 0},
        0.7: {"count": 0, "wins": 0},
        0.8: {"count": 0, "wins": 0},
        0.9: {"count": 0, "wins": 0}
    }
    
    print("Evaluating Math Model Accuracy...")
    
    for bet in settled_bets:
        # We need actual scores to determine who won
        # For simplicity in this eval, if bet 'result' is win/loss, we know the outcome relative to the bet.
        # But we really need the actual game outcome. Let's assume the side bet on is what we have data for.
        # Actually Hoops Edge `bets` table doesn't natively store the final score. 
        # But we know if the bet 'result' is 'win' or 'loss'.
        
        home = bet["home_team"]
        away = bet["away_team"]
        
        home_stats = stats_map.get(home, {})
        away_stats = stats_map.get(away, {})
        
        res = project_matchup(away_stats, home_stats, is_neutral_site=False)
        
        # Calculate Brier Score and Accuracy
        # To do this perfectly we need exact game scores in the DB.
        # Since we don't store exact final scores in `bets`, we can just output the average predicted margin of victory for bets that won vs lost.
        # A more advanced eval would fetch the historical boxscore.
        
        total_games += 1
        
        # For demonstration of the Eval framework:
        proj_home_win = res["home_win_prob"] > 0.5
        
        # Determine empirical outcome based on bet
        # If the user bet HOME and won, or AWAY and lost -> HOME WON
        # If the user bet AWAY and won, or HOME and lost -> AWAY WON
        # Note: This is a proxy for Moneyline. Spreads require actual margin.
        side = bet["side"].upper()
        result = bet["result"]
        
        home_actually_won = None
        if side == "HOME":
            home_actually_won = True if result == "win" else False
        elif side == "AWAY":
            home_actually_won = False if result == "win" else True
        else:
            # Skip OVER/UNDER for pure head-to-head win eval
            continue
            
        # Accuracy
        if proj_home_win == home_actually_won:
            correct_predictions += 1
            
        # Brier Score = (predicted_prob - actual_outcome)^2
        actual_val = 1.0 if home_actually_won else 0.0
        brier_score_sum += (res["home_win_prob"] - actual_val) ** 2
        
        # Calibration Bins (grouping probabilities from 0.5 to 1.0 for the favored team)
        favored_prob = max(res["home_win_prob"], res["away_win_prob"])
        favored_actually_won = (home_actually_won and proj_home_win) or (not home_actually_won and not proj_home_win)
        
        for p_bin in sorted(calibration_bins.keys(), reverse=True):
            if favored_prob >= p_bin:
                calibration_bins[p_bin]["count"] += 1
                if favored_actually_won:
                    calibration_bins[p_bin]["wins"] += 1
                break

    if total_games == 0:
        print("No Moneyline or Spread bets could be resolved to a straight-up winner for evaluation.")
        return
        
    accuracy = correct_predictions / total_games
    brier_score = brier_score_sum / total_games
    
    print("\n# 📊 Model Quantitative Evaluation Report\n")
    print(f"**Total Games Evaluated:** {total_games}")
    print(f"**Straight-Up Accuracy:** {accuracy*100:.1f}%")
    print(f"**Brier Score:** {brier_score:.3f} *(lower is better, 0.25 is random guessing)*\n")
    
    print("## Probability Calibration")
    print("*(When the model predicts X% chance of winning, how often does that team actually win?)*\n")
    print("| Predicted Probability Range | Actual Win % | Sample Size |")
    print("|---|---|---|")
    for p_bin in sorted(calibration_bins.keys()):
        data = calibration_bins[p_bin]
        upper_bound = p_bin + 0.1
        if data["count"] > 0:
            actual_pct = (data["wins"] / data["count"]) * 100
            print(f"| {p_bin*100:.0f}% - {upper_bound*100:.0f}% | {actual_pct:.1f}% | {data['count']} games |")
        else:
            print(f"| {p_bin*100:.0f}% - {upper_bound*100:.0f}% | N/A | 0 games |")


if __name__ == "__main__":
    run_backtest()
