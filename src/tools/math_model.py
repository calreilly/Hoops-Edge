"""
Mathematical projection engine for college basketball matchups.
Uses Adjusted Offensive (AdjO), Adjusted Defensive (AdjD), and Pace stats
to estimate expected possessions, final scores, and win probabilities.
"""

from typing import Dict, Any
import math

# Standard NCAA average efficiency is historically around 105.0. 
NCAA_AVG_EFFICIENCY = 105.0
# Standard deviation for college basketball point spreads is historically ~10.5
CBB_STDEV = 10.5

def normal_cdf(x: float) -> float:
    """Approximate the standard normal CDF using math.erf."""
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0

def project_matchup(away_stats: Dict[str, Any], home_stats: Dict[str, Any], is_neutral_site: bool = True) -> Dict[str, Any]:
    """
    Project the outcome of a matchup given the efficiency stats of both teams.
    
    Stats dictionaries should contain:
    - 'adj_o': float
    - 'adj_d': float
    - 'pace': float
    
    Returns a dictionary with projected scores, spread, and win probabilities.
    """
    # Extract stats, defaulting to average if missing or malformed
    away_o = float(away_stats.get("adj_o", NCAA_AVG_EFFICIENCY))
    away_d = float(away_stats.get("adj_d", NCAA_AVG_EFFICIENCY))
    away_p = float(away_stats.get("pace", 68.0))
    
    home_o = float(home_stats.get("adj_o", NCAA_AVG_EFFICIENCY))
    home_d = float(home_stats.get("adj_d", NCAA_AVG_EFFICIENCY))
    home_p = float(home_stats.get("pace", 68.0))

    # 1. Project Pace (Expected Possessions)
    # Average the paces of the two teams
    expected_possessions = (away_p + home_p) / 2.0

    # 2. Project Efficiency (Points per 100 possessions)
    # Log5 approximation technique: (Team O * Opponent D) / League Avg
    away_proj_eff = (away_o * home_d) / NCAA_AVG_EFFICIENCY
    home_proj_eff = (home_o * away_d) / NCAA_AVG_EFFICIENCY

    # 3. Project Scores
    away_score = away_proj_eff * (expected_possessions / 100.0)
    home_score = home_proj_eff * (expected_possessions / 100.0)

    # 4. Add Home Court Advantage (HCA) to points if not neutral site
    # Typically HCA is worth ~3.5 points total
    if not is_neutral_site:
        home_score += 1.75
        away_score -= 1.75

    # 5. Calculate Spread (Home Team perspective)
    # Positive means Home scored more.
    projected_home_margin = home_score - away_score

    # 6. Calculate Win Probability using normal distribution CDF
    # z-score = (expected margin - 0) / stdev
    # We want home win probability, so P(Home Margin > 0)
    home_win_prob = normal_cdf(projected_home_margin / CBB_STDEV)
    away_win_prob = 1.0 - home_win_prob

    return {
        "away_score": round(away_score, 1),
        "home_score": round(home_score, 1),
        "projected_margin": round(projected_home_margin, 2), # positive = home wins, negative = away wins
        "expected_possessions": round(expected_possessions, 1),
        "home_win_prob": round(home_win_prob, 3),
        "away_win_prob": round(away_win_prob, 3)
    }
