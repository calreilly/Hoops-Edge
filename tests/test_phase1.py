"""
Phase 1 Tests — EV Calculator and Storage
Run: pytest tests/
"""
from datetime import datetime, timedelta
import pytest

from src.models.schemas import (
    Odds, BetType, BetSide, TeamStats, Game, EVAnalysis, BetRecommendation
)
from src.db.storage import BetLedger


# ── Odds Math Tests ────────────────────────────────────────────────────────────

def test_implied_probability_favorite():
    """A -110 line should imply ~52.38% probability."""
    odds = Odds(sportsbook="fanduel", bet_type=BetType.SPREAD, side=BetSide.HOME,
                line=-7.5, american_odds=-110)
    assert abs(odds.implied_probability - 0.5238) < 0.001

def test_implied_probability_underdog():
    """+150 underdog should imply ~40% probability."""
    odds = Odds(sportsbook="fanduel", bet_type=BetType.MONEYLINE, side=BetSide.AWAY,
                line=None, american_odds=150)
    assert abs(odds.implied_probability - 0.40) < 0.001

def test_decimal_odds_conversion():
    """-110 American = ~1.909 decimal."""
    odds = Odds(sportsbook="fanduel", bet_type=BetType.SPREAD, side=BetSide.HOME,
                line=-3.5, american_odds=-110)
    assert abs(odds.decimal_odds - 1.9091) < 0.001


# ── BetRecommendation Validation ───────────────────────────────────────────────

def test_bet_recommendation_cap_units_on_low_ev():
    """Bets with EV < 2% should be auto-capped at 1.0 units."""
    rec = BetRecommendation(
        game_id="test_game",
        home_team="UConn",
        away_team="Villanova",
        game_time=datetime.now() + timedelta(hours=5),
        bet_type=BetType.SPREAD,
        side=BetSide.HOME,
        line=-7.5,
        american_odds=-110,
        ev_analysis=EVAnalysis(
            bet_type=BetType.SPREAD,
            side=BetSide.HOME,
            reasoning_steps=["Step 1", "Step 2", "Step 3"],
            projected_win_probability=0.54,
            implied_probability=0.5238,
            expected_value=0.015,  # Only 1.5% EV — below threshold
            confidence=0.6,
        ),
        recommended_units=3.0,  # Would normally be 3u, should be capped
        is_recommended=True,
        summary="Test bet with marginal edge.",
    )
    assert rec.recommended_units <= 1.0


# ── Database Tests ─────────────────────────────────────────────────────────────

def test_bet_ledger_init(tmp_path):
    """BetLedger should init tables and seed bankroll."""
    db_path = str(tmp_path / "test.db")
    ledger = BetLedger(db_path=db_path)
    bankroll = ledger.get_bankroll()
    assert bankroll["balance_units"] == 100.0

def test_save_and_retrieve_bet(tmp_path):
    """Should save a BetRecommendation and retrieve it as pending."""
    db_path = str(tmp_path / "test.db")
    ledger = BetLedger(db_path=db_path)

    rec = BetRecommendation(
        game_id="test_001",
        home_team="Duke",
        away_team="UNC",
        game_time=datetime.now() + timedelta(hours=3),
        bet_type=BetType.SPREAD,
        side=BetSide.AWAY,
        line=-3.5,
        american_odds=-112,
        ev_analysis=EVAnalysis(
            bet_type=BetType.SPREAD,
            side=BetSide.AWAY,
            reasoning_steps=["Duke elite offense", "UNC weak perimeter D", "Duke -3.5 is fair value"],
            projected_win_probability=0.60,
            implied_probability=0.5283,
            expected_value=0.062,
            confidence=0.70,
        ),
        recommended_units=1.5,
        is_recommended=True,
        summary="Duke elite offense exploits UNC perimeter weakness.",
    )

    bet_id = ledger.save_recommendation(rec)
    pending = ledger.get_pending_bets()
    assert len(pending) == 1
    assert pending[0]["game_id"] == "test_001"
    assert pending[0]["status"] == "pending"

def test_approve_bet(tmp_path):
    """Approving a bet should change status to approved."""
    db_path = str(tmp_path / "test.db")
    ledger = BetLedger(db_path=db_path)

    rec = BetRecommendation(
        game_id="test_002",
        home_team="Gonzaga",
        away_team="Saint Mary's",
        game_time=datetime.now() + timedelta(hours=5),
        bet_type=BetType.TOTAL,
        side=BetSide.OVER,
        line=145.5,
        american_odds=-108,
        ev_analysis=EVAnalysis(
            bet_type=BetType.TOTAL,
            side=BetSide.OVER,
            reasoning_steps=["Both teams run high pace", "Both top-15 offenses", "Expected 148pt game"],
            projected_win_probability=0.58,
            implied_probability=0.5189,
            expected_value=0.051,
            confidence=0.65,
        ),
        recommended_units=1.2,
        is_recommended=True,
        summary="Both teams' pace and elite offenses push total over 145.5.",
    )
    bet_id = ledger.save_recommendation(rec)
    ledger.approve_bet(bet_id)
    approved = ledger.get_approved_bets()
    assert len(approved) == 1

def test_team_stats_upsert(tmp_path):
    """Should upsert team stats correctly."""
    db_path = str(tmp_path / "test.db")
    ledger = BetLedger(db_path=db_path)

    stats = TeamStats(
        team_name="UConn Huskies",
        team_id="uconn",
        record="22-3",
        offensive_efficiency=118.4,
        defensive_efficiency=94.2,
        pace=67.1,
        three_point_rate=0.33,
        ats_record="14-11",
        conference="Big East",
    )
    ledger.upsert_team_stats(stats)
    result = ledger.get_team_stats("uconn")
    assert result["team_name"] == "UConn Huskies"
    assert result["offensive_efficiency"] == 118.4
