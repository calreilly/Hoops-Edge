"""
Live Odds Client — The-Odds-API
Fetches real FanDuel NCAAB spreads, totals, and moneylines.
API docs: https://the-odds-api.com/liveapi/guides/v4/

Free tier: 500 requests/month (~16/day).
Each --slate run costs 2 requests (spreads + totals).
"""
import os
import requests
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

from src.models.schemas import Game, Odds, BetType, BetSide, TeamStats
from src.db.storage import BetLedger

load_dotenv()

ODDS_API_KEY = os.getenv("ODDS_API_KEY")
BASE_URL = "https://api.the-odds-api.com/v4"
SPORT = "basketball_ncaab"
FANDUEL_KEY = "fanduel"


def _american_to_model(
    sportsbook: str,
    bet_type: BetType,
    side: BetSide,
    price: int,
    point: Optional[float] = None,
) -> Odds:
    return Odds(
        sportsbook=sportsbook,
        bet_type=bet_type,
        side=side,
        line=point,
        american_odds=price,
    )


def fetch_fanduel_ncaab_odds() -> list[dict]:
    """
    Fetch raw odds from The-Odds-API for today's NCAAB games on FanDuel.
    Returns the raw JSON list from the API.
    Raises RuntimeError if the API key is missing or request fails.
    """
    if not ODDS_API_KEY:
        raise RuntimeError(
            "ODDS_API_KEY is not set. Add it to your .env file.\n"
            "Get a free key at: https://the-odds-api.com"
        )

    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "us",
        "markets": "spreads,totals,h2h",
        "bookmakers": FANDUEL_KEY,
        "oddsFormat": "american",
        "dateFormat": "iso",
    }

    resp = requests.get(f"{BASE_URL}/sports/{SPORT}/odds", params=params, timeout=10)

    # Log remaining quota from response headers
    remaining = resp.headers.get("x-requests-remaining", "?")
    used = resp.headers.get("x-requests-used", "?")
    print(f"  [Odds API] Requests used: {used} | Remaining: {remaining}")

    if resp.status_code != 200:
        raise RuntimeError(f"Odds API error {resp.status_code}: {resp.text}")

    return resp.json()


def _lookup_team_stats(team_name: str, ledger: BetLedger) -> Optional[TeamStats]:
    """
    Try to match a team name from the API to a record in our team_stats DB.
    Fuzzy-matches on the last word (e.g. 'Huskies' matches 'UConn Huskies').
    """
    all_stats = ledger.get_all_team_stats()
    name_lower = team_name.lower()
    for row in all_stats:
        stored = row["team_name"].lower()
        # Exact match
        if stored == name_lower:
            return TeamStats(**{k: v for k, v in row.items() if k != "last_updated"})
        # Partial match — last word of either direction
        if name_lower.split()[-1] in stored or stored.split()[-1] in name_lower:
            return TeamStats(**{k: v for k, v in row.items() if k != "last_updated"})
    return None


def parse_odds_response(raw_games: list[dict], ledger: BetLedger) -> list[Game]:
    """
    Transform The-Odds-API JSON into our Game Pydantic models,
    pulling team stats from the local SQLite DB if available.
    """
    games: list[Game] = []

    for raw in raw_games:
        home_team = raw["home_team"]
        away_team = raw["away_team"]
        game_time = datetime.fromisoformat(raw["commence_time"].replace("Z", "+00:00"))
        game_id = raw["id"]

        # Initialize odds slots
        home_spread: Optional[Odds] = None
        away_spread: Optional[Odds] = None
        over_odds: Optional[Odds] = None
        under_odds: Optional[Odds] = None
        home_ml: Optional[Odds] = None
        away_ml: Optional[Odds] = None

        # Parse bookmaker (FanDuel)
        for bookmaker in raw.get("bookmakers", []):
            if bookmaker["key"] != FANDUEL_KEY:
                continue

            for market in bookmaker.get("markets", []):
                mkey = market["key"]

                if mkey == "spreads":
                    for outcome in market["outcomes"]:
                        side = BetSide.HOME if outcome["name"] == home_team else BetSide.AWAY
                        odds_obj = _american_to_model(
                            FANDUEL_KEY, BetType.SPREAD, side,
                            int(outcome["price"]), outcome.get("point")
                        )
                        if side == BetSide.HOME:
                            home_spread = odds_obj
                        else:
                            away_spread = odds_obj

                elif mkey == "totals":
                    for outcome in market["outcomes"]:
                        side = BetSide.OVER if outcome["name"] == "Over" else BetSide.UNDER
                        odds_obj = _american_to_model(
                            FANDUEL_KEY, BetType.TOTAL, side,
                            int(outcome["price"]), outcome.get("point")
                        )
                        if side == BetSide.OVER:
                            over_odds = odds_obj
                        else:
                            under_odds = odds_obj

                elif mkey == "h2h":
                    for outcome in market["outcomes"]:
                        side = BetSide.HOME if outcome["name"] == home_team else BetSide.AWAY
                        odds_obj = _american_to_model(
                            FANDUEL_KEY, BetType.MONEYLINE, side,
                            int(outcome["price"])
                        )
                        if side == BetSide.HOME:
                            home_ml = odds_obj
                        else:
                            away_ml = odds_obj

        # Skip games with no FanDuel lines at all
        if not any([home_spread, away_spread, over_odds, under_odds]):
            print(f"  [Odds API] Skipping {away_team} @ {home_team} — no FanDuel lines found")
            continue

        # Look up team stats from our DB
        home_stats = _lookup_team_stats(home_team, ledger)
        away_stats = _lookup_team_stats(away_team, ledger)

        games.append(Game(
            game_id=game_id,
            home_team=home_team,
            away_team=away_team,
            game_time=game_time,
            home_odds=home_spread,
            away_odds=away_spread,
            total_over_odds=over_odds,
            total_under_odds=under_odds,
            home_stats=home_stats,
            away_stats=away_stats,
            injury_notes="Live game — see ESPN for latest injury news.",
        ))

    return games


def get_live_games(ledger: BetLedger) -> list[Game]:
    """
    Main entry point: fetch today's real NCAAB FanDuel slate.
    Falls back to mock data if ODDS_API_KEY is not set.
    """
    if not ODDS_API_KEY:
        print("  ⚠️  ODDS_API_KEY not set — falling back to mock data.")
        print("  Get a free key at: https://the-odds-api.com\n")
        from src.tools.mock_odds import get_mock_games
        return get_mock_games()

    raw = fetch_fanduel_ncaab_odds()
    games = parse_odds_response(raw, ledger)

    if not games:
        print("  ℹ️  No NCAAB games with FanDuel lines today. Using mock data.")
        from src.tools.mock_odds import get_mock_games
        return get_mock_games()

    print(f"  ✅ Fetched {len(games)} live NCAAB games from FanDuel.\n")
    return games
