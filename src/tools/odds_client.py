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
from zoneinfo import ZoneInfo

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
    Match a team name from the Odds API to a record in our team_stats DB.

    Strategy (in order):
      1. Exact match (case-insensitive)
      2. ≥2 meaningful words overlap between API name and stored name
      3. No match → return None (never assign stats to the wrong team)

    Single-word mascot matches (e.g. 'Tigers', 'Devils') are intentionally
    rejected to prevent assigning P5 stats to low-major programs.
    """
    # Words that appear in many team names and should not count as meaningful
    STOP_WORDS = {"st", "state", "the", "of", "at", "university", "college",
                  "a&m", "u", "nc", "pa", "ny", "la"}

    all_stats = ledger.get_all_team_stats()
    if not all_stats:
        return None

    name_lower = team_name.lower()
    name_words = {w for w in name_lower.split() if w not in STOP_WORDS}

    best_match = None
    best_score = 0

    for row in all_stats:
        stored = row["team_name"].lower()

        # 1. Exact match
        if stored == name_lower:
            return TeamStats(**{k: v for k, v in row.items() if k != "last_updated"})

        # 2. Word-overlap scoring
        stored_words = {w for w in stored.split() if w not in STOP_WORDS}
        overlap = name_words & stored_words
        score = len(overlap)

        if score > best_score:
            best_score = score
            best_match = row

    # Require at least 2 meaningful word matches to accept
    if best_score >= 2 and best_match is not None:
        return TeamStats(**{k: v for k, v in best_match.items() if k != "last_updated"})

    # No confident match — return None so the agent gets no stats
    # (better to say "no data" than to give wrong data)
    return None


ET = ZoneInfo("America/New_York")


def fetch_live_rankings() -> dict[str, int]:
    """
    Fetch the current AP Top 25 poll from ESPN's free public API.
    Returns {team_display_name_lower: rank}.
    Falls back to empty dict on any failure — never crashes the caller.
    """
    try:
        resp = requests.get(
            "https://site.api.espn.com/apis/site/v2/sports/basketball/"
            "mens-college-basketball/rankings",
            timeout=5,
        )
        if resp.status_code != 200:
            print(f"  [Rankings] ESPN returned {resp.status_code} — skipping ranking update.")
            return {}
        data = resp.json()
        rankings: dict[str, int] = {}
        for poll in data.get("rankings", []):
            if "AP" not in poll.get("name", ""):
                continue
            for entry in poll.get("ranks", []):
                rank = entry.get("current", 0)
                team = entry.get("team", {})
                loc = team.get("location", "")
                nickname = team.get("name", "")
                name = f"{loc} {nickname}".strip()
                if name and rank:
                    rankings[name.lower()] = rank
        print(f"  [Rankings] {len(rankings)} AP Top 25 teams from ESPN.")
        return rankings
    except Exception as e:
        print(f"  [Rankings] Fetch failed: {e}")
        return {}


def _apply_live_ranking(
    stats: Optional[TeamStats],
    team_name: str,
    live_rankings: dict[str, int],
) -> Optional[TeamStats]:
    """
    Overwrite stats.ranking with the live AP rank if a name match is found.
    Clears stale ranking if team is no longer ranked.
    """
    if stats is None or not live_rankings:
        return stats
    name_lower = team_name.lower()
    for key, rank in live_rankings.items():
        overlap = set(key.split()) & set(name_lower.split())
        if len(overlap) >= 2:
            return stats.model_copy(update={"ranking": rank})
    # Team not found in live poll — clear any stale ranking
    return stats.model_copy(update={"ranking": None})



def parse_odds_response(
    raw_games: list[dict],
    ledger: BetLedger,
    live_rankings: Optional[dict] = None,
) -> list[Game]:
    """
    Transform The-Odds-API JSON into our Game Pydantic models,
    pulling team stats from the local SQLite DB if available.
    live_rankings: optional {team_name_lower: rank} from fetch_live_rankings().
    """
    games: list[Game] = []

    for raw in raw_games:
        home_team = raw["home_team"]
        away_team = raw["away_team"]
        game_time = datetime.fromisoformat(
            raw["commence_time"].replace("Z", "+00:00")
        ).astimezone(ET)  # convert UTC → Eastern
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

        # Look up team stats from our DB, then apply live AP rankings
        home_stats = _apply_live_ranking(
            _lookup_team_stats(home_team, ledger), home_team, live_rankings or {}
        )
        away_stats = _apply_live_ranking(
            _lookup_team_stats(away_team, ledger), away_team, live_rankings or {}
        )

        games.append(Game(
            game_id=game_id,
            home_team=home_team,
            away_team=away_team,
            game_time=game_time,
            home_odds=home_spread,
            away_odds=away_spread,
            total_over_odds=over_odds,
            total_under_odds=under_odds,
            home_ml=home_ml,
            away_ml=away_ml,
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

    # Fetch live AP rankings BEFORE parsing odds (zero cost, no auth)
    live_rankings = fetch_live_rankings()

    raw = fetch_fanduel_ncaab_odds()
    games = parse_odds_response(raw, ledger, live_rankings=live_rankings)

    if not games:
        print("  ℹ️  No NCAAB games with FanDuel lines today. Using mock data.")
        from src.tools.mock_odds import get_mock_games
        return get_mock_games()

    print(f"  ✅ Fetched {len(games)} live NCAAB games from FanDuel.\n")
    return games
