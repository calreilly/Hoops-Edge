"""
Phase 1: Mock Odds Data
Returns realistic test games so the EV agent can be tested without a paid API key.
In Phase 3 (Week 9), this module is replaced by the real MCP Odds Server.
"""
from datetime import datetime, timedelta
from src.models.schemas import Game, Odds, BetType, BetSide, TeamStats


def get_mock_games() -> list[Game]:
    """Returns a list of realistic mock CBB games for testing."""
    tomorrow = datetime.now().replace(hour=19, minute=0, second=0, microsecond=0) + timedelta(days=1)

    games = [
        Game(
            game_id="ncaab_20260223_uconn_vill",
            home_team="UConn Huskies",
            away_team="Villanova Wildcats",
            game_time=tomorrow,
            home_odds=Odds(
                sportsbook="fanduel",
                bet_type=BetType.SPREAD,
                side=BetSide.HOME,
                line=-7.5,
                american_odds=-110,
            ),
            away_odds=Odds(
                sportsbook="fanduel",
                bet_type=BetType.SPREAD,
                side=BetSide.AWAY,
                line=7.5,
                american_odds=-110,
            ),
            total_over_odds=Odds(
                sportsbook="fanduel",
                bet_type=BetType.TOTAL,
                side=BetSide.OVER,
                line=138.5,
                american_odds=-112,
            ),
            total_under_odds=Odds(
                sportsbook="fanduel",
                bet_type=BetType.TOTAL,
                side=BetSide.UNDER,
                line=138.5,
                american_odds=-108,
            ),
            home_stats=TeamStats(
                team_name="UConn Huskies",
                team_id="uconn",
                record="22-3",
                offensive_efficiency=118.4,
                defensive_efficiency=94.2,
                pace=67.1,
                three_point_rate=0.33,
                ats_record="14-11",
                conference="Big East",
            ),
            away_stats=TeamStats(
                team_name="Villanova Wildcats",
                team_id="villanova",
                record="14-11",
                offensive_efficiency=105.2,
                defensive_efficiency=102.8,
                pace=63.4,
                three_point_rate=0.41,
                ats_record="12-13",
                conference="Big East",
            ),
            injury_notes="Villanova: G Mark Armstrong questionable (ankle). UConn: full strength.",
        ),
        Game(
            game_id="ncaab_20260223_duke_unc",
            home_team="North Carolina Tar Heels",
            away_team="Duke Blue Devils",
            game_time=tomorrow + timedelta(hours=2),
            home_odds=Odds(
                sportsbook="fanduel",
                bet_type=BetType.SPREAD,
                side=BetSide.HOME,
                line=3.5,
                american_odds=-108,
            ),
            away_odds=Odds(
                sportsbook="fanduel",
                bet_type=BetType.SPREAD,
                side=BetSide.AWAY,
                line=-3.5,
                american_odds=-112,
            ),
            total_over_odds=Odds(
                sportsbook="fanduel",
                bet_type=BetType.TOTAL,
                side=BetSide.OVER,
                line=155.5,
                american_odds=-110,
            ),
            total_under_odds=Odds(
                sportsbook="fanduel",
                bet_type=BetType.TOTAL,
                side=BetSide.UNDER,
                line=155.5,
                american_odds=-110,
            ),
            home_stats=TeamStats(
                team_name="North Carolina Tar Heels",
                team_id="unc",
                record="17-8",
                offensive_efficiency=112.1,
                defensive_efficiency=99.6,
                pace=71.8,
                three_point_rate=0.38,
                ats_record="15-10",
                conference="ACC",
            ),
            away_stats=TeamStats(
                team_name="Duke Blue Devils",
                team_id="duke",
                record="21-4",
                offensive_efficiency=120.3,
                defensive_efficiency=95.1,
                pace=70.2,
                three_point_rate=0.36,
                ats_record="13-12",
                conference="ACC",
            ),
            injury_notes="No significant injuries reported for either team.",
        ),
    ]
    return games
