from src.tools.odds_client import fetch_fanduel_ncaab_odds
raw = fetch_fanduel_ncaab_odds()
for g in raw:
    home = g["home_team"]
    away = g["away_team"]
    if any(x in home for x in ["Nebraska", "Maryland", "Alabama", "Arkansas", "Vanderbilt"]) or any(x in away for x in ["Nebraska", "Maryland", "Alabama", "Arkansas", "Vanderbilt"]):
        print(f"\nGame: {away} @ {home}")
        for b in g.get("bookmakers", []):
            if b["key"] == "fanduel":
                for m in b["markets"]:
                    if m["key"] == "h2h":
                        print("H2H Outcomes:", [o["name"] for o in m["outcomes"]])

