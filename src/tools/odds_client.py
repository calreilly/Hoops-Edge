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
FANDUEL_KEY = "fanduel"
TRACKED_BOOKS = "fanduel,draftkings,betmgm,caesars"


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


def fetch_odds_for_sport(sport_key: str) -> list[dict]:
    """
    Fetch raw odds from The-Odds-API for today's games on multiple tracked sportsbooks.
    Returns the raw JSON list from the API for the given sport_key.
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
        "bookmakers": TRACKED_BOOKS,
        "oddsFormat": "american",
        "dateFormat": "iso",
    }

    resp = requests.get(f"{BASE_URL}/sports/{sport_key}/odds", params=params, timeout=10)

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
      2. Strict Subset Match or Jaccard Similarity >= 0.6
      3. No match → return None (never assign stats to the wrong team)

    Single-word mascot matches (e.g. 'Tigers', 'Devils') are intentionally
    rejected to prevent assigning P5 stats to low-major programs.
    """
    import string
    
    # Words that appear in many team names and should not count as meaningful
    STOP_WORDS = {"st", "state", "the", "of", "at", "university", "college",
                  "a&m", "u", "nc", "pa", "ny", "la"}

    all_stats = ledger.get_all_team_stats()
    if not all_stats:
        return None

    name_lower = team_name.lower()
    
    # Fast exact match check first
    for row in all_stats:
        if row["team_name"].lower() == name_lower:
            return TeamStats(**{k: v for k, v in row.items() if k != "last_updated"})

    # Fuzzy Match setup
    clean_name = name_lower.translate(str.maketrans('', '', string.punctuation))
    name_words = {w for w in clean_name.split() if w not in STOP_WORDS}

    best_match = None
    best_score = 0
    best_jaccard = 0

    for row in all_stats:
        stored = row["team_name"].lower()
        clean_stored = stored.translate(str.maketrans('', '', string.punctuation))
        stored_words = {w for w in clean_stored.split() if w not in STOP_WORDS}

        overlap = name_words & stored_words
        score = len(overlap)

        if score > best_score:
            best_score = score
            best_match = row
            
            union_len = len(name_words | stored_words)
            best_jaccard = score / union_len if union_len > 0 else 0

    if best_match is not None:
        clean_stored = best_match["team_name"].lower().translate(str.maketrans('', '', string.punctuation))
        best_stored_words = {w for w in clean_stored.split() if w not in STOP_WORDS}
        
        is_subset = best_stored_words.issubset(name_words) or name_words.issubset(best_stored_words)
        
        # Accept if it's a perfect subset (e.g. "Duke" inside "Duke Blue Devils") 
        # or if they heavily overlap (Jaccard >= 0.6)
        if is_subset or best_jaccard >= 0.6:
            return TeamStats(**{k: v for k, v in best_match.items() if k != "last_updated"})

    # No confident match — return None so the agent gets no stats
    # (better to say "no data" than to give wrong data)
    return None

ET = ZoneInfo("America/New_York")


def fetch_live_rankings() -> dict[str, tuple[int, str]]:
    """
    Fetch the current AP Top 25 poll from ESPN's free public API.
    Returns {team_display_name_lower: (rank, record)}.
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
        rankings: dict[str, tuple[int, str]] = {}
        for poll in data.get("rankings", []):
            if "AP" not in poll.get("name", ""):
                continue
            for entry in poll.get("ranks", []):
                rank = entry.get("current", 0)
                team = entry.get("team", {})
                loc = team.get("location", "")
                nickname = team.get("name", "")
                record = entry.get("recordSummary", "0-0")
                name = f"{loc} {nickname}".strip()
                if name and rank:
                    rankings[name.lower()] = (rank, record)
        print(f"  [Rankings] {len(rankings)} AP Top 25 teams from ESPN.")
        return rankings
    except Exception as e:
        print(f"  [Rankings] Fetch failed: {e}")
        return {}


def fetch_daily_records() -> dict[str, str]:
    """
    Fetch the current scoreboard to get the latest records for all unranked teams playing today.
    Returns {team_name_lower: "Wins-Losses"}.
    """
    try:
        resp = requests.get(
            "https://site.api.espn.com/apis/site/v2/sports/basketball/"
            "mens-college-basketball/scoreboard?limit=400",
            timeout=5,
        )
        if resp.status_code != 200:
            return {}
        
        data = resp.json()
        daily_records: dict[str, str] = {}
        for e in data.get("events", []):
            for c in e.get("competitions", []):
                for t in c.get("competitors", []):
                    team = t.get("team", {})
                    loc = team.get("location", "")
                    nickname = team.get("name", "")
                    name = f"{loc} {nickname}".strip().lower()
                    
                    records = t.get("records", [])
                    overall = "0-0"
                    for r in records:
                        if r.get("type") in ["summary", "total"] or r.get("name") == "overall":
                            overall = r.get("summary", "0-0")
                    if name:
                        daily_records[name] = overall
        return daily_records
    except Exception as e:
        print(f"  [Records] Fetch failed: {e}")
        return {}


def _apply_live_ranking(
    stats: Optional[TeamStats],
    team_name: str,
    live_rankings: dict[str, tuple[int, str]],
) -> Optional[TeamStats]:
    """
    Overwrite stats.ranking with the live AP rank if a name match is found.
    Clears stale ranking if team is no longer ranked.
    """
    if not live_rankings:
        return stats
        
    STOP_WORDS = {"st.", "st", "state", "the", "of", "at", "university", "college",
                  "a&m", "u", "nc", "pa", "ny", "la"}

    name_lower = team_name.lower()
    name_words = {w for w in name_lower.split() if w not in STOP_WORDS}
    
    for key, (rank, record) in live_rankings.items():
        key_words = {w for w in key.split() if w not in STOP_WORDS}
        overlap = key_words & name_words
        if len(overlap) >= 2 or (len(key_words) > 0 and len(overlap) == len(key_words)):
            # If we don't have stats yet, make a dummy one just so the rank can be attached
            if stats is None:
                stats = TeamStats(
                    team_id=team_name,
                    team_name=team_name,
                    record=record,
                    last_updated=datetime.now()
                )
            return stats.model_copy(update={"ranking": rank, "record": record})
            
    # Team not found in live poll — clear any stale ranking
    return stats.model_copy(update={"ranking": None}) if stats else None



def parse_odds_response(
    raw_games: list[dict],
    ledger: BetLedger,
    live_rankings: Optional[dict] = None,
    daily_records: Optional[dict[str, str]] = None,
    sport_key: str = "basketball_ncaab"
) -> list[Game]:
    """
    Transform The-Odds-API JSON into our Game Pydantic models,
    pulling team stats from the local SQLite DB if available.
    live_rankings: optional {team_name_lower: (rank, record)} from fetch_live_rankings().
    daily_records: optional {team_name_lower: record} from fetch_daily_records().
    """
    games: list[Game] = []

    for raw in raw_games:
        home_team = raw["home_team"]
        away_team = raw["away_team"]
        game_time = datetime.fromisoformat(
            raw["commence_time"].replace("Z", "+00:00")
        ).astimezone(ET)  # convert UTC → Eastern
        
        # Strictly filter to only include games played today
        if game_time.date() != datetime.now(ET).date():
            continue
            
        game_id = raw["id"]

        # Initialize odds slots
        home_spread: dict[str, Odds] = {}
        away_spread: dict[str, Odds] = {}
        over_odds: dict[str, Odds] = {}
        under_odds: dict[str, Odds] = {}
        home_ml: dict[str, Odds] = {}
        away_ml: dict[str, Odds] = {}

        # Parse tracked bookmakers
        tracked_keys = TRACKED_BOOKS.split(",")
        for bookmaker in raw.get("bookmakers", []):
            bkey = bookmaker["key"]
            if bkey not in tracked_keys:
                continue

            for market in bookmaker.get("markets", []):
                mkey = market["key"]

                if mkey == "spreads":
                    for outcome in market["outcomes"]:
                        side = BetSide.HOME if outcome["name"] == home_team else BetSide.AWAY
                        odds_obj = _american_to_model(
                            bkey, BetType.SPREAD, side,
                            int(outcome["price"]), outcome.get("point")
                        )
                        if side == BetSide.HOME:
                            home_spread[bkey] = odds_obj
                        else:
                            away_spread[bkey] = odds_obj

                elif mkey == "totals":
                    for outcome in market["outcomes"]:
                        side = BetSide.OVER if outcome["name"] == "Over" else BetSide.UNDER
                        odds_obj = _american_to_model(
                            bkey, BetType.TOTAL, side,
                            int(outcome["price"]), outcome.get("point")
                        )
                        if side == BetSide.OVER:
                            over_odds[bkey] = odds_obj
                        else:
                            under_odds[bkey] = odds_obj

                elif mkey == "h2h":
                    for outcome in market["outcomes"]:
                        side = BetSide.HOME if outcome["name"] == home_team else BetSide.AWAY
                        odds_obj = _american_to_model(
                            bkey, BetType.MONEYLINE, side,
                            int(outcome["price"])
                        )
                        if side == BetSide.HOME:
                            home_ml[bkey] = odds_obj
                        else:
                            away_ml[bkey] = odds_obj

        # Skip games with no lines at all from any tracked bookmaker
        if not home_spread and not away_spread and not over_odds and not under_odds and not home_ml and not away_ml:
            print(f"  [Odds API] Skipping {away_team} @ {home_team} — no lines found")
            continue

        # Look up team stats from our DB, then apply live AP rankings
        home_stats = _apply_live_ranking(
            _lookup_team_stats(home_team, ledger), home_team, live_rankings or {}
        )
        away_stats = _apply_live_ranking(
            _lookup_team_stats(away_team, ledger), away_team, live_rankings or {}
        )
        
        # Fallback for unranked teams not in local DB: use daily_records
        # Use word-boundary matching to avoid 'Maryland' → 'Maryland-Eastern Shore'
        import re as _re
        def _match_record(team_name: str, records: dict[str, str]) -> str:
            needle = team_name.lower()
            candidates = [
                (abs(len(t) - len(needle)), r)
                for t, r in records.items()
                if _re.search(r'\b' + _re.escape(needle) + r'\b', t)
            ]
            if candidates:
                return sorted(candidates)[0][1]  # shortest delta = most specific match
            return "0-0"

        if home_stats is None and daily_records:
            hr = _match_record(home_team, daily_records)
            home_stats = TeamStats(team_id=home_team, team_name=home_team, record=hr, last_updated=datetime.now())
            
        if away_stats is None and daily_records:
            ar = _match_record(away_team, daily_records)
            away_stats = TeamStats(team_id=away_team, team_name=away_team, record=ar, last_updated=datetime.now())

        games.append(Game(
            game_id=game_id,
            sport_key=sport_key,
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


def get_live_games(ledger: BetLedger, sport_keys: list[str] = ["basketball_ncaab"]) -> list[Game]:
    """
    Main entry point: fetch today's real slate for the given sports.
    Iterates through the requested sports and concats them.
    Falls back to mock data if ODDS_API_KEY is not set.
    """
    if not ODDS_API_KEY:
        print("  ⚠️  ODDS_API_KEY not set — falling back to mock data.")
        print("  Get a free key at: https://the-odds-api.com\n")
        from src.tools.mock_odds import get_mock_games
        return get_mock_games()

    live_rankings = fetch_live_rankings()
    daily_records = fetch_daily_records()

    all_games = []
    
    for sport in sport_keys:
        try:
            raw = fetch_odds_for_sport(sport)
            games = parse_odds_response(raw, ledger, live_rankings=live_rankings, daily_records=daily_records, sport_key=sport)
            all_games.extend(games)
            print(f"  ✅ Fetched {len(games)} live {sport} games from FanDuel.")
        except Exception as e:
            print(f"  ❌ Error fetching {sport}: {e}")

    if not all_games:
        print("  ℹ️  No games with FanDuel lines today across requested sports. Using mock data.")
        from src.tools.mock_odds import get_mock_games
        return get_mock_games()

    print(f"\n  ✅ Combined Slate: {len(all_games)} games ready for EV Analysis.\n")
    return all_games
