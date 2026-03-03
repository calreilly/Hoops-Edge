import requests
from datetime import datetime

def get_completed_games():
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?limit=400"
    try:
        data = requests.get(url, timeout=5).json()
        completed = {}
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
                    # Need both location and nickname
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
                    completed[f"{away_team} @ {home_team}"] = {"home_score": home_score, "away_score": away_score}
        return completed
    except Exception as e:
        print(f"Error: {e}")
        return {}

if __name__ == "__main__":
    games = get_completed_games()
    print(f"Found {len(games)} completed games today.")
    for k, v in list(games.items())[:5]:
        print(f"{k} -> {v['away_score']} - {v['home_score']}")
