"""
Phase 1 - Week 3: PydanticAI Schemas
Strictly typed data models for the Hoops Edge CBB betting agent.
"""
from __future__ import annotations
from pydantic import BaseModel, Field, model_validator
from typing import Optional, List
from enum import Enum
from datetime import datetime


class BetType(str, Enum):
    SPREAD = "spread"
    MONEYLINE = "moneyline"
    TOTAL = "total"
    PLAYER_PROP = "player_prop"


class BetSide(str, Enum):
    HOME = "home"
    AWAY = "away"
    OVER = "over"
    UNDER = "under"


class TeamStats(BaseModel):
    """Historical performance stats for a team (stored in DB for Week 4)."""
    team_name: str
    team_id: str  # e.g., ESPN or KenPom ID
    record: str = Field(..., description="e.g. '15-5'")
    offensive_efficiency: Optional[float] = Field(None, description="Points per 100 possessions")
    defensive_efficiency: Optional[float] = Field(None, description="Points allowed per 100 possessions")
    pace: Optional[float] = Field(None, description="Possessions per 40 minutes")
    three_point_rate: Optional[float] = Field(None, description="3PA / FGA ratio")
    ats_record: Optional[str] = Field(None, description="Against the spread record, e.g. '12-8'")
    conference: Optional[str] = None
    last_updated: Optional[datetime] = None


class Odds(BaseModel):
    """Represents a single side/market line from a sportsbook."""
    sportsbook: str = Field(default="fanduel", description="The sportsbook offering the line")
    bet_type: BetType
    side: BetSide
    line: Optional[float] = Field(None, description="Spread or total line, e.g. -3.5 or 142.5")
    american_odds: int = Field(..., description="American odds, e.g. -110, +145")

    @property
    def implied_probability(self) -> float:
        """Convert American odds to implied probability (no-vig approximation)."""
        if self.american_odds < 0:
            return abs(self.american_odds) / (abs(self.american_odds) + 100)
        else:
            return 100 / (self.american_odds + 100)

    @property
    def decimal_odds(self) -> float:
        """Convert American odds to decimal format."""
        if self.american_odds < 0:
            return 1 + (100 / abs(self.american_odds))
        else:
            return 1 + (self.american_odds / 100)


class Game(BaseModel):
    """Represents a scheduled CBB game with both sides' lines."""
    game_id: str
    home_team: str
    away_team: str
    game_time: datetime
    home_odds: Optional[Odds] = None       # spread
    away_odds: Optional[Odds] = None       # spread
    total_over_odds: Optional[Odds] = None
    total_under_odds: Optional[Odds] = None
    home_ml: Optional[Odds] = None         # moneyline
    away_ml: Optional[Odds] = None         # moneyline
    home_stats: Optional[TeamStats] = None
    away_stats: Optional[TeamStats] = None
    injury_notes: Optional[str] = Field(None, description="Plain-text summary of relevant injuries")


class EVAnalysis(BaseModel):
    """
    Intermediate reasoning output from the EV Calculator agent.
    Week 2: This is the Chain-of-Thought artifact.
    """
    bet_type: BetType
    side: BetSide
    reasoning_steps: List[str] = Field(
        ...,
        description="Step-by-step CoT reasoning for the probability estimate"
    )
    projected_win_probability: float = Field(
        ..., ge=0.0, le=1.0,
        description="Agent's estimated win probability for this side (0.0-1.0)"
    )
    implied_probability: float = Field(
        ..., ge=0.0, le=1.0,
        description="Sportsbook's implied probability derived from the odds"
    )
    expected_value: float = Field(
        ...,
        description="EV = (proj_prob * decimal_odds) - 1. Positive = +EV"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0,
        description="Agent's confidence in its own probability estimate (0.0-1.0)"
    )


class BetRecommendation(BaseModel):
    """
    Final structured output from the agent.
    Week 3: This is what gets written to the DB and shown in the UI.
    """
    game_id: str
    home_team: str
    away_team: str
    game_time: datetime
    bet_type: BetType
    side: BetSide
    line: Optional[float] = None
    american_odds: int
    ev_analysis: EVAnalysis
    recommended_units: float = Field(
        ..., ge=0.0, le=5.0,
        description="Kelly-fraction adjusted stake in units (max 5u)"
    )
    is_recommended: bool = Field(
        ...,
        description="True if EV > threshold AND confidence is sufficient"
    )
    summary: str = Field(
        ...,
        description="One-sentence human-readable rationale for the bet"
    )

    @model_validator(mode="after")
    def enforce_quality_thresholds(self) -> BetRecommendation:
        """
        Post-processing guardrails applied after Kelly sizing:
          1. EV threshold — suppress bets below +3.5% EV (within model error margin)
          2. Unit floor  — suppress bets where Kelly gives < 0.05u (noise bets)
        """
        ev = self.ev_analysis.expected_value
        # (1) EV threshold
        if ev < 0.035:
            self.is_recommended = False
            self.recommended_units = 0.0
        # (2) Unit floor — even if EV passes, don't bother with micro-stakes
        if self.recommended_units < 0.05 and self.recommended_units > 0.0:
            self.is_recommended = False
            self.recommended_units = 0.0
        return self


class DailySlate(BaseModel):
    """Container for all recommendations on a given day."""
    date: str  # YYYY-MM-DD
    games_analyzed: int
    bets: List[BetRecommendation]
    total_units_at_risk: float

    @model_validator(mode="after")
    def deduplicate_opposite_sides(self) -> DailySlate:
        """
        Safety: if both sides of the same market are recommended
        (e.g. UConn -7.5 AND Villanova +7.5 both fire as +EV),
        keep only the one with higher expected_value and flag the other.
        This prevents betting against ourselves on the same game.
        """
        # Group recommended bets by (game_id, bet_type)
        from collections import defaultdict
        groups: dict = defaultdict(list)
        for bet in self.bets:
            if bet.is_recommended:
                key = (bet.game_id, bet.bet_type)
                groups[key].append(bet)

        # For each group with >1 recommended, keep the best EV, suppress the rest
        for key, group_bets in groups.items():
            if len(group_bets) > 1:
                # Sort by EV descending; keep the top one
                group_bets.sort(
                    key=lambda b: b.ev_analysis.expected_value, reverse=True
                )
                for loser in group_bets[1:]:
                    loser.is_recommended = False
                    loser.summary = (
                        f"[SUPPRESSED — opposite side also +EV] {loser.summary}"
                    )

        # Recalculate total units after dedup
        self.total_units_at_risk = sum(
            b.recommended_units for b in self.bets if b.is_recommended
        )
        return self

    @property
    def positive_ev_bets(self) -> List[BetRecommendation]:
        return [b for b in self.bets if b.is_recommended]

