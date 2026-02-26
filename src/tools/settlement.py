import requests
import string
from src.db.storage import BetLedger
from src.models.schemas import BetType, BetSide

def fetch_completed_scores() -> dict:
    """
    Fetch the current NCAAB scoreboard from ESPN.
    Returns completed games as a list of dictionaries with standardized home/away lowercase names and scores.
    """
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?limit=400"
    completed = []
    try:
        data = requests.get(url, timeout=5).json()
        for e in data.get("events", []):
            status = e.get("status", {}).get("type", {}).get("state", "")
            if status != "post":
                continue # only completed games
            
            for c in e.get("competitions", []):
                home_team = None
                away_team = None
                home_score = 0
                away_score = 0
                
                for t in c.get("competitors", []):
                    team = t.get("team", {})
                    loc = team.get("location", "")
                    nickname = team.get("name", "")
                    name = f"{loc} {nickname}".strip().lower()
                    score = int(t.get("score", "0"))
                    
                    if t.get("homeAway") == "home":
                        home_team = name
                        home_score = score
                    else:
                        away_team = name
                        away_score = score
                
                if home_team and away_team:
                    completed.append({
                        "home_team": home_team,
                        "away_team": away_team,
                        "home_score": home_score,
                        "away_score": away_score
                    })
        return completed
    except Exception as e:
        print(f"Error fetching scores: {e}")
        return []

def _normalize_name(name: str) -> set:
    """Convert team name to lowercase stripped word set for fuzzy matching."""
    STOP_WORDS = {"st.", "st", "state", "the", "of", "at", "university", "college",
                  "a&m", "u", "nc", "pa", "ny", "la"}
    word_set = set()
    for w in name.lower().split():
        clean = w.translate(str.maketrans('', '', string.punctuation))
        if clean not in STOP_WORDS:
            word_set.add(clean)
    return word_set

def _match_game(bet_away: str, bet_home: str, espn_games: list) -> dict:
    """Find the best matching ESPN game for the bet's teams."""
    bet_away_words = _normalize_name(bet_away)
    bet_home_words = _normalize_name(bet_home)
    
    for game in espn_games:
        espn_away_words = _normalize_name(game["away_team"])
        espn_home_words = _normalize_name(game["home_team"])
        
        # Check overlap
        if (len(bet_away_words & espn_away_words) >= 1) and (len(bet_home_words & espn_home_words) >= 1):
            return game
            
    return None

def auto_settle_pending_bets(ledger: BetLedger) -> tuple[int, int, int]:
    """
    Attempt to auto-settle any pending bets by scraping ESPN for completed scores.
    Returns (wins, losses, pushes) settled in this run.
    """
    completed_games = fetch_completed_scores()
    if not completed_games:
        return 0, 0, 0
        
    pending = ledger.get_pending_bets()
    wins_count = 0
    losses_count = 0
    pushes_count = 0
    
    for bet in pending:
        # Match game
        espn_game = _match_game(bet["away_team"], bet["home_team"], completed_games)
        if not espn_game:
            continue
            
        home_score = espn_game["home_score"]
        away_score = espn_game["away_score"]
        
        btype = bet["bet_type"]
        side = bet["side"]
        line = bet["line"]
        units = bet["recommended_units"]
        american_odds = bet["american_odds"]
        
        # Determine multiplier for profit if win
        # (e.g., +150 means 1.5x, -110 means 1/1.1 = 0.909x)
        profit_multiplier = 0.0
        if american_odds > 0:
            profit_multiplier = american_odds / 100.0
        else:
            profit_multiplier = 100.0 / abs(american_odds)
            
        result = None
        profit_loss = 0.0
        
        if btype == BetType.MONEYLINE.value:
            if side == BetSide.HOME.value:
                if home_score > away_score: result = "win"
                elif home_score < away_score: result = "loss"
                else: result = "push"
            else:
                if away_score > home_score: result = "win"
                elif away_score < home_score: result = "loss"
                else: result = "push"
                
        elif btype == BetType.SPREAD.value:
            if side == BetSide.HOME.value:
                margin = home_score + line - away_score
                if margin > 0: result = "win"
                elif margin < 0: result = "loss"
                else: result = "push"
            else:
                margin = away_score + line - home_score
                if margin > 0: result = "win"
                elif margin < 0: result = "loss"
                else: result = "push"
                
        elif btype == BetType.TOTAL.value:
            total = home_score + away_score
            if side == BetSide.OVER.value:
                if total > line: result = "win"
                elif total < line: result = "loss"
                else: result = "push"
            else:
                if total < line: result = "win"
                elif total > line: result = "loss"
                else: result = "push"
                
        # Update accounting
        if result == "win":
            profit_loss = units * profit_multiplier
            wins_count += 1
        elif result == "loss":
            profit_loss = -units
            losses_count += 1
        elif result == "push":
            profit_loss = 0.0
            pushes_count += 1
            
        if result:
            ledger.settle_bet(bet["id"], result, profit_loss)
            
    return wins_count, losses_count, pushes_count
