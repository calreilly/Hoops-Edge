"""
ESPN Public API Client
Free, no auth required. Used for Teams Explorer page.
All endpoints: site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball
"""
import requests
from typing import Optional

BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball"
TIMEOUT = 6


def _get(url: str) -> Optional[dict]:
    try:
        r = requests.get(url, timeout=TIMEOUT)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[ESPN] {url} → {e}")
    return None


def logo_url(espn_id: int) -> str:
    return f"https://a.espncdn.com/i/teamlogos/ncaa/500/{espn_id}.png"


def fetch_team_summary(espn_id: int) -> dict:
    """Team name, record, logo."""
    d = _get(f"{BASE}/teams/{espn_id}")
    if not d:
        return {}
    t = d.get("team", {})
    logos = t.get("logos", [])
    record_items = t.get("record", {}).get("items", [])
    record = record_items[0].get("summary", "") if record_items else ""
    return {
        "espn_id": espn_id,
        "name": t.get("displayName", ""),
        "shortName": t.get("shortDisplayName", ""),
        "logo": logos[0]["href"] if logos else logo_url(espn_id),
        "color": t.get("color", "1a2236"),
        "alternateColor": t.get("alternateColor", "f97316"),
        "record": record,
        "location": t.get("location", ""),
        "nickname": t.get("nickname", ""),
    }


def fetch_team_roster(espn_id: int) -> list[dict]:
    """Return list of player dicts."""
    d = _get(f"{BASE}/teams/{espn_id}/roster")
    if not d:
        return []
    players = []
    for a in d.get("athletes", []):
        stats = {}
        for s in a.get("statistics", {}).get("splits", {}).get("categories", []):
            for stat in s.get("stats", []):
                stats[stat.get("abbreviation", "")] = stat.get("displayValue", "")
        players.append({
            "id": a.get("id"),
            "name": a.get("displayName", ""),
            "jersey": a.get("jersey", ""),
            "position": a.get("position", {}).get("abbreviation", ""),
            "year": a.get("experience", {}).get("displayValue", ""),
            "height": a.get("height", ""),
            "weight": a.get("weight", ""),
            "headshot": a.get("headshot", {}).get("href", ""),
            "stats": stats,
        })
    return players


def fetch_team_schedule(espn_id: int) -> list[dict]:
    """Return list of game dicts for current season."""
    d = _get(f"{BASE}/teams/{espn_id}/schedule")
    if not d:
        return []
    games = []
    for ev in d.get("events", []):
        comp = ev.get("competitions", [{}])[0]
        status = comp.get("status", {})
        status_type = status.get("type", {})
        completed = status_type.get("completed", False)

        # Score
        home_score = away_score = None
        home_name = away_name = ""
        for c in comp.get("competitors", []):
            if c.get("homeAway") == "home":
                home_name = c.get("team", {}).get("displayName", "")
                home_score = c.get("score")
            else:
                away_name = c.get("team", {}).get("displayName", "")
                away_score = c.get("score")

        games.append({
            "event_id": ev.get("id"),
            "date": ev.get("date", ""),
            "name": ev.get("shortName", ev.get("name", "")),
            "home": home_name,
            "away": away_name,
            "home_score": home_score,
            "away_score": away_score,
            "completed": completed,
            "status": status_type.get("shortDetail", status_type.get("description", "")),
        })
    return games


def fetch_boxscore(event_id: str) -> dict:
    """Return simplified box score for a completed game."""
    d = _get(f"{BASE}/summary?event={event_id}")
    if not d:
        return {}

    teams_box = []
    for team_data in d.get("boxscore", {}).get("teams", []):
        team_name = team_data.get("team", {}).get("displayName", "")
        players_rows = []
        for cat in team_data.get("statistics", []):
            if cat.get("name") == "":
                continue
            for p in cat.get("athletes", []):
                athlete = p.get("athlete", {})
                players_rows.append({
                    "name": athlete.get("displayName", ""),
                    "position": athlete.get("position", {}).get("abbreviation", ""),
                    "stats": [s.get("displayValue", "") for s in p.get("stats", [])],
                    "labels": [s.get("abbreviation", "") for s in p.get("stats", [])],
                })
            if players_rows:
                break  # just first category (usually starters + bench)

        teams_box.append({"team": team_name, "players": players_rows})

    header = d.get("header", {})
    comps = header.get("competitions", [{}])
    result_str = ""
    if comps:
        comp = comps[0]
        for c in comp.get("competitors", []):
            result_str += f"{c.get('team',{}).get('displayName','')} {c.get('score','')},  "

    return {
        "result": result_str.strip(", "),
        "teams": teams_box,
        "headlines": [h.get("shortLinkText", h.get("description",""))
                      for h in d.get("news", {}).get("articles", [])[:2]],
    }


def fetch_player_stats(player_id: str) -> dict:
    """Return career/season stats and bio for a player."""
    d = _get(f"https://site.api.espn.com/apis/site/v2/sports/basketball/"
             f"mens-college-basketball/athletes/{player_id}")
    if not d:
        return {}
    a = d.get("athlete", d)
    stats_d = _get(f"https://site.api.espn.com/apis/site/v2/sports/basketball/"
                   f"mens-college-basketball/athletes/{player_id}/statisticslog")
    # Simplified — return bio + whatever stats are in summary
    return {
        "name": a.get("displayName", ""),
        "position": a.get("position", {}).get("displayName", ""),
        "headshot": a.get("headshot", {}).get("href", ""),
        "weight": a.get("weight", ""),
        "height": a.get("height", ""),
        "birthPlace": a.get("birthPlace", {}).get("city", ""),
        "college": a.get("college", {}).get("name", ""),
        "stats_raw": stats_d or {},
    }


# ── ESPN ID map for our 30 seeded teams ────────────────────────────────────────
# Used to build the Teams Explorer grid
TEAM_ESPN_IDS: dict[str, int] = {
    "Auburn Tigers":             2,
    "Houston Cougars":           248,
    "Duke Blue Devils":          150,
    "Tennessee Volunteers":      2633,
    "Florida Gators":            57,
    "Iowa State Cyclones":       66,
    "Kansas Jayhawks":           2305,
    "Gonzaga Bulldogs":          2250,
    "Arizona Wildcats":          12,
    "Illinois Fighting Illini":  356,
    "Purdue Boilermakers":       2509,
    "St. John's Red Storm":      2597,
    "Texas Tech Red Raiders":    2641,
    "UConn Huskies":             41,
    "Michigan State Spartans":   127,
    "Kentucky Wildcats":         96,
    "Marquette Golden Eagles":   269,
    "Creighton Bluejays":        156,
    "BYU Cougars":               252,
    "Baylor Bears":              239,
    "North Carolina Tar Heels":  153,
    "Dayton Flyers":             167,
    "Seton Hall Pirates":        2550,
    "Ohio State Buckeyes":       194,
    "Oklahoma Sooners":          201,
    "Louisville Cardinals":      97,
    "Memphis Tigers":            235,
    "Pittsburgh Panthers":       221,
    "Wichita State Shockers":    2724,
    "Villanova Wildcats":        222,
}
