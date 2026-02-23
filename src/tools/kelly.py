"""
Phase 1 Enhancement: Kelly Criterion Post-Processor
Applies hard math on top of the agent's recommended_units to ensure
correct quarter-Kelly sizing — not relying on the LLM to do the math.
"""


def quarter_kelly_units(
    projected_prob: float,
    decimal_odds: float,
    max_units: float = 3.0,
    fraction: float = 0.25,
) -> float:
    """
    Computes the quarter-Kelly stake in units.

    Formula:
        full_kelly = (p * decimal_odds - 1) / (decimal_odds - 1)
        quarter_kelly = full_kelly * fraction

    Args:
        projected_prob: Agent's estimated win probability (0.0–1.0)
        decimal_odds:   e.g. 1.909 for -110
        max_units:      Hard cap (default 3.0u)
        fraction:       Kelly fraction (default 0.25 = quarter-Kelly)

    Returns:
        Recommended units, capped at max_units. Returns 0.0 if math is -EV.
    """
    if decimal_odds <= 1.0:
        return 0.0

    edge = (projected_prob * decimal_odds) - 1.0
    if edge <= 0:
        # Mathematically -EV; Kelly says bet 0
        return 0.0

    full_kelly = edge / (decimal_odds - 1.0)
    units = full_kelly * fraction
    return min(round(units, 2), max_units)


def apply_kelly_to_recommendation(rec) -> None:
    """
    Mutates a BetRecommendation in-place: overwrites recommended_units
    with the hard-computed quarter-Kelly value.

    Odds are known (american_odds on the rec), and projected_prob comes
    from the agent's EVAnalysis. This prevents the LLM from hallucinating
    an incorrect unit size.
    """
    from src.models.schemas import BetRecommendation

    # Compute decimal odds from american odds
    ao = rec.american_odds
    if ao < 0:
        decimal_odds = 1 + (100 / abs(ao))
    else:
        decimal_odds = 1 + (ao / 100)

    proj_prob = rec.ev_analysis.projected_win_probability
    kelly_units = quarter_kelly_units(proj_prob, decimal_odds)

    # Override whatever the LLM said
    rec.recommended_units = kelly_units
