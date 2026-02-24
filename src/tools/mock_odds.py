"""
Phase 1: Mock Odds Data
Returns a full 8-game slate of realistic CBB matchups.
In Phase 3 (Week 9), this is replaced by the real MCP Odds Server.
"""
from datetime import datetime, timedelta
from src.models.schemas import Game, Odds, BetType, BetSide, TeamStats


def _game_time(hours_from_now: float) -> datetime:
    base = datetime.now().replace(minute=0, second=0, microsecond=0)
    return base + timedelta(hours=hours_from_now)


def get_mock_games() -> list[Game]:
    """Returns a realistic 8-game CBS slate for testing."""

    return [
        # ── Game 1: Big East ──────────────────────────────────────────────────
        Game(
            game_id="ncaab_uconn_villanova",
            home_team="UConn Huskies",
            away_team="Villanova Wildcats",
            game_time=_game_time(6),
            home_odds=Odds(sportsbook="fanduel", bet_type=BetType.SPREAD, side=BetSide.HOME, line=-7.5, american_odds=-110),
            away_odds=Odds(sportsbook="fanduel", bet_type=BetType.SPREAD, side=BetSide.AWAY, line=7.5, american_odds=-110),
            total_over_odds=Odds(sportsbook="fanduel", bet_type=BetType.TOTAL, side=BetSide.OVER, line=138.5, american_odds=-112),
            total_under_odds=Odds(sportsbook="fanduel", bet_type=BetType.TOTAL, side=BetSide.UNDER, line=138.5, american_odds=-108),
            home_stats=TeamStats(team_name="UConn Huskies", team_id="uconn", record="22-3",
                offensive_efficiency=118.4, defensive_efficiency=94.2, pace=67.1,
                three_point_rate=0.33, ats_record="14-11", conference="Big East"),
            away_stats=TeamStats(team_name="Villanova Wildcats", team_id="villanova", record="14-11",
                offensive_efficiency=105.2, defensive_efficiency=102.8, pace=63.4,
                three_point_rate=0.41, ats_record="12-13", conference="Big East"),
            injury_notes="Villanova: G Mark Armstrong questionable (ankle). UConn: full strength.",
        ),

        # ── Game 2: ACC Rivalry ───────────────────────────────────────────────
        Game(
            game_id="ncaab_duke_unc",
            home_team="North Carolina Tar Heels",
            away_team="Duke Blue Devils",
            game_time=_game_time(8),
            home_odds=Odds(sportsbook="fanduel", bet_type=BetType.SPREAD, side=BetSide.HOME, line=3.5, american_odds=-108),
            away_odds=Odds(sportsbook="fanduel", bet_type=BetType.SPREAD, side=BetSide.AWAY, line=-3.5, american_odds=-112),
            total_over_odds=Odds(sportsbook="fanduel", bet_type=BetType.TOTAL, side=BetSide.OVER, line=155.5, american_odds=-110),
            total_under_odds=Odds(sportsbook="fanduel", bet_type=BetType.TOTAL, side=BetSide.UNDER, line=155.5, american_odds=-110),
            home_stats=TeamStats(team_name="North Carolina Tar Heels", team_id="unc", record="17-8",
                offensive_efficiency=112.1, defensive_efficiency=99.6, pace=71.8,
                three_point_rate=0.38, ats_record="15-10", conference="ACC"),
            away_stats=TeamStats(team_name="Duke Blue Devils", team_id="duke", record="21-4",
                offensive_efficiency=120.3, defensive_efficiency=95.1, pace=70.2,
                three_point_rate=0.36, ats_record="13-12", conference="ACC"),
            injury_notes="No significant injuries for either team.",
        ),

        # ── Game 3: SEC Matchup ───────────────────────────────────────────────
        Game(
            game_id="ncaab_auburn_tennessee",
            home_team="Auburn Tigers",
            away_team="Tennessee Volunteers",
            game_time=_game_time(7),
            home_odds=Odds(sportsbook="fanduel", bet_type=BetType.SPREAD, side=BetSide.HOME, line=-4.5, american_odds=-110),
            away_odds=Odds(sportsbook="fanduel", bet_type=BetType.SPREAD, side=BetSide.AWAY, line=4.5, american_odds=-110),
            total_over_odds=Odds(sportsbook="fanduel", bet_type=BetType.TOTAL, side=BetSide.OVER, line=134.5, american_odds=-108),
            total_under_odds=Odds(sportsbook="fanduel", bet_type=BetType.TOTAL, side=BetSide.UNDER, line=134.5, american_odds=-112),
            home_stats=TeamStats(team_name="Auburn Tigers", team_id="auburn", record="22-3",
                offensive_efficiency=119.8, defensive_efficiency=93.5, pace=73.4,
                three_point_rate=0.37, ats_record="17-8", conference="SEC"),
            away_stats=TeamStats(team_name="Tennessee Volunteers", team_id="tennessee", record="21-4",
                offensive_efficiency=113.6, defensive_efficiency=91.2, pace=66.8,
                three_point_rate=0.31, ats_record="15-10", conference="SEC"),
            injury_notes="Tennessee: PG Dalton Knecht probable (soreness). Auburn: full strength.",
        ),

        # ── Game 4: Big 12 ────────────────────────────────────────────────────
        Game(
            game_id="ncaab_houston_iowa-st",
            home_team="Houston Cougars",
            away_team="Iowa State Cyclones",
            game_time=_game_time(9),
            home_odds=Odds(sportsbook="fanduel", bet_type=BetType.SPREAD, side=BetSide.HOME, line=-3.5, american_odds=-110),
            away_odds=Odds(sportsbook="fanduel", bet_type=BetType.SPREAD, side=BetSide.AWAY, line=3.5, american_odds=-110),
            total_over_odds=Odds(sportsbook="fanduel", bet_type=BetType.TOTAL, side=BetSide.OVER, line=131.5, american_odds=-110),
            total_under_odds=Odds(sportsbook="fanduel", bet_type=BetType.TOTAL, side=BetSide.UNDER, line=131.5, american_odds=-110),
            home_stats=TeamStats(team_name="Houston Cougars", team_id="houston", record="22-3",
                offensive_efficiency=116.7, defensive_efficiency=90.4, pace=65.3,
                three_point_rate=0.32, ats_record="17-8", conference="Big 12"),
            away_stats=TeamStats(team_name="Iowa State Cyclones", team_id="iowa-st", record="20-5",
                offensive_efficiency=115.9, defensive_efficiency=95.8, pace=68.2,
                three_point_rate=0.39, ats_record="14-11", conference="Big 12"),
            injury_notes="No significant injuries reported.",
        ),

        # ── Game 5: Big Ten ───────────────────────────────────────────────────
        Game(
            game_id="ncaab_purdue_illinois",
            home_team="Illinois Fighting Illini",
            away_team="Purdue Boilermakers",
            game_time=_game_time(5),
            home_odds=Odds(sportsbook="fanduel", bet_type=BetType.SPREAD, side=BetSide.HOME, line=5.5, american_odds=-108),
            away_odds=Odds(sportsbook="fanduel", bet_type=BetType.SPREAD, side=BetSide.AWAY, line=-5.5, american_odds=-112),
            total_over_odds=Odds(sportsbook="fanduel", bet_type=BetType.TOTAL, side=BetSide.OVER, line=142.5, american_odds=-110),
            total_under_odds=Odds(sportsbook="fanduel", bet_type=BetType.TOTAL, side=BetSide.UNDER, line=142.5, american_odds=-110),
            home_stats=TeamStats(team_name="Illinois Fighting Illini", team_id="illinois", record="19-6",
                offensive_efficiency=115.8, defensive_efficiency=97.3, pace=67.6,
                three_point_rate=0.36, ats_record="14-11", conference="Big Ten"),
            away_stats=TeamStats(team_name="Purdue Boilermakers", team_id="purdue", record="21-4",
                offensive_efficiency=121.5, defensive_efficiency=97.8, pace=66.4,
                three_point_rate=0.36, ats_record="15-10", conference="Big Ten"),
            injury_notes="Purdue: C Zach Edey day-to-day (back). Illinois: F Coleman Hawkins questionable.",
        ),

        # ── Game 6: Big East ──────────────────────────────────────────────────
        Game(
            game_id="ncaab_st-johns_marquette",
            home_team="St. John's Red Storm",
            away_team="Marquette Golden Eagles",
            game_time=_game_time(6.5),
            home_odds=Odds(sportsbook="fanduel", bet_type=BetType.SPREAD, side=BetSide.HOME, line=-2.5, american_odds=-110),
            away_odds=Odds(sportsbook="fanduel", bet_type=BetType.SPREAD, side=BetSide.AWAY, line=2.5, american_odds=-110),
            total_over_odds=Odds(sportsbook="fanduel", bet_type=BetType.TOTAL, side=BetSide.OVER, line=148.5, american_odds=-110),
            total_under_odds=Odds(sportsbook="fanduel", bet_type=BetType.TOTAL, side=BetSide.UNDER, line=148.5, american_odds=-110),
            home_stats=TeamStats(team_name="St. John's Red Storm", team_id="st-johns", record="21-4",
                offensive_efficiency=116.1, defensive_efficiency=96.5, pace=71.0,
                three_point_rate=0.36, ats_record="15-10", conference="Big East"),
            away_stats=TeamStats(team_name="Marquette Golden Eagles", team_id="marquette", record="19-6",
                offensive_efficiency=114.3, defensive_efficiency=98.7, pace=70.5,
                three_point_rate=0.40, ats_record="13-12", conference="Big East"),
            injury_notes="Marquette: G Tyler Kolek questionable (hamstring). St. John's: full strength.",
        ),

        # ── Game 7: WCC vs Big 12 ─────────────────────────────────────────────
        Game(
            game_id="ncaab_gonzaga_arizona",
            home_team="Arizona Wildcats",
            away_team="Gonzaga Bulldogs",
            game_time=_game_time(10),
            home_odds=Odds(sportsbook="fanduel", bet_type=BetType.SPREAD, side=BetSide.HOME, line=1.5, american_odds=-110),
            away_odds=Odds(sportsbook="fanduel", bet_type=BetType.SPREAD, side=BetSide.AWAY, line=-1.5, american_odds=-110),
            total_over_odds=Odds(sportsbook="fanduel", bet_type=BetType.TOTAL, side=BetSide.OVER, line=158.5, american_odds=-110),
            total_under_odds=Odds(sportsbook="fanduel", bet_type=BetType.TOTAL, side=BetSide.UNDER, line=158.5, american_odds=-110),
            home_stats=TeamStats(team_name="Arizona Wildcats", team_id="arizona", record="20-5",
                offensive_efficiency=119.2, defensive_efficiency=96.0, pace=71.3,
                three_point_rate=0.35, ats_record="14-11", conference="Big 12"),
            away_stats=TeamStats(team_name="Gonzaga Bulldogs", team_id="gonzaga", record="23-2",
                offensive_efficiency=122.7, defensive_efficiency=96.3, pace=72.1,
                three_point_rate=0.34, ats_record="16-9", conference="WCC"),
            injury_notes="Gonzaga: F Drew Timme limited (knee). Arizona: no injuries.",
        ),

        # ── Game 8: Big 12 Low-Spread ─────────────────────────────────────────
        Game(
            game_id="ncaab_kansas_baylor",
            home_team="Kansas Jayhawks",
            away_team="Baylor Bears",
            game_time=_game_time(7.5),
            home_odds=Odds(sportsbook="fanduel", bet_type=BetType.SPREAD, side=BetSide.HOME, line=-2.5, american_odds=-115),
            away_odds=Odds(sportsbook="fanduel", bet_type=BetType.SPREAD, side=BetSide.AWAY, line=2.5, american_odds=-105),
            total_over_odds=Odds(sportsbook="fanduel", bet_type=BetType.TOTAL, side=BetSide.OVER, line=146.5, american_odds=-110),
            total_under_odds=Odds(sportsbook="fanduel", bet_type=BetType.TOTAL, side=BetSide.UNDER, line=146.5, american_odds=-110),
            home_stats=TeamStats(team_name="Kansas Jayhawks", team_id="kansas", record="20-5",
                offensive_efficiency=117.2, defensive_efficiency=97.4, pace=69.3,
                three_point_rate=0.35, ats_record="13-12", conference="Big 12"),
            away_stats=TeamStats(team_name="Baylor Bears", team_id="baylor", record="18-7",
                offensive_efficiency=113.2, defensive_efficiency=98.9, pace=70.4,
                three_point_rate=0.37, ats_record="13-12", conference="Big 12"),
            injury_notes="Both teams fully healthy.",
        ),
    ]
