"""
ESPN Public API Client
Free, no auth required. Used for Teams Explorer page.
All endpoints: site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball
"""
import requests
from typing import Optional

BASE_URLS = {
    "basketball_ncaab": "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball",
    "basketball_ncaaw": "https://site.api.espn.com/apis/site/v2/sports/basketball/womens-college-basketball",
    "basketball_nba": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
}
TIMEOUT = 6


def _get(url: str) -> Optional[dict]:
    try:
        r = requests.get(url, timeout=TIMEOUT)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[ESPN] {url} → {e}")
    return None


def logo_url(espn_id: int, sport_key: str = "basketball_ncaab") -> str:
    if "nba" in sport_key:
        return f"https://a.espncdn.com/i/teamlogos/nba/500/{espn_id}.png"
    return f"https://a.espncdn.com/i/teamlogos/ncaa/500/{espn_id}.png"


def fetch_team_summary(espn_id: int, sport_key: str = "basketball_ncaab") -> dict:
    """Team name, record, ranking, conference standing, home/road splits."""
    base = BASE_URLS.get(sport_key, BASE_URLS["basketball_ncaab"])
    d = _get(f"{base}/teams/{espn_id}")
    if not d:
        return {}
    t = d.get("team", {})
    logos = t.get("logos", [])

    # Parse all record splits: total, home, road
    record_map: dict[str, str] = {}
    for item in t.get("record", {}).get("items", []):
        rtype   = item.get("type", "total")
        summary = item.get("summary", "")
        if summary:
            record_map[rtype] = summary

    return {
        "espn_id":       espn_id,
        "name":          t.get("displayName", ""),
        "shortName":     t.get("shortDisplayName", ""),
        "logo":          logos[0]["href"] if logos else logo_url(espn_id, sport_key),
        "color":         t.get("color", "1a2236"),
        "alternateColor":t.get("alternateColor", "f97316"),
        "record":        record_map.get("total", ""),
        "home_record":   record_map.get("home", ""),
        "road_record":   record_map.get("road", ""),
        "location":      t.get("location", ""),
        "nickname":      t.get("nickname", ""),
        "rank":          t.get("rank"),           # AP rank or None
        "standing":      t.get("standingSummary", ""),  # e.g. "2nd in Big East"
    }


def fetch_team_roster(espn_id: int, sport_key: str = "basketball_ncaab") -> list[dict]:
    """Return list of player dicts."""
    base = BASE_URLS.get(sport_key, BASE_URLS["basketball_ncaab"])
    d = _get(f"{base}/teams/{espn_id}/roster")
    if not d:
        return []
    players = []
    for a in d.get("athletes", []):
        stats = {}
        for s in a.get("statistics", {}).get("splits", {}).get("categories", []):
            for stat in s.get("stats", []):
                stats[stat.get("abbreviation", "")] = stat.get("displayValue", "")
                
        # Handle dict vs string structures for bio data
        headshot_raw = a.get("headshot", "")
        headshot = headshot_raw.get("href", "") if isinstance(headshot_raw, dict) else headshot_raw
        
        bp_raw = a.get("birthPlace", "")
        birthplace = bp_raw.get("city", "") if isinstance(bp_raw, dict) else bp_raw
        
        pos_raw = a.get("position", {})
        position = pos_raw.get("abbreviation", "") if isinstance(pos_raw, dict) else pos_raw

        exp_raw = a.get("experience", {})
        year = exp_raw.get("displayValue", "") if isinstance(exp_raw, dict) else exp_raw

        players.append({
            "id": a.get("id"),
            "name": a.get("displayName", ""),
            "jersey": a.get("jersey", ""),
            "position": position,
            "year": year,
            "height": a.get("displayHeight", a.get("height", "")),
            "weight": a.get("displayWeight", a.get("weight", "")),
            "headshot": headshot,
            "birthPlace": birthplace,
            "stats": stats,
        })
    return players


def fetch_team_schedule(espn_id: int, sport_key: str = "basketball_ncaab") -> list[dict]:
    """Return list of game dicts for current season."""
    base = BASE_URLS.get(sport_key, BASE_URLS["basketball_ncaab"])
    d = _get(f"{base}/teams/{espn_id}/schedule")
    if not d:
        return []
    games = []

    def _score(raw) -> Optional[str]:
        """Extract display score string from ESPN score field (may be dict or str)."""
        if raw is None:
            return None
        if isinstance(raw, dict):
            return raw.get("displayValue") or str(int(raw.get("value", 0)))
        return str(raw)

    for ev in d.get("events", []):
        comp = ev.get("competitions", [{}])[0]
        status = comp.get("status", {})
        status_type = status.get("type", {})
        completed = status_type.get("completed", False)

        home_score = away_score = None
        home_name = away_name = ""
        team_is_home = False
        for c in comp.get("competitors", []):
            is_home = c.get("homeAway") == "home"
            name = c.get("team", {}).get("displayName", "")
            score = _score(c.get("score"))
            if is_home:
                home_name = name
                home_score = score
            else:
                away_name = name
                away_score = score
            # Detect which side is "our" team
            if c.get("team", {}).get("id") == str(espn_id):
                team_is_home = is_home

        games.append({
            "event_id": ev.get("id"),
            "date": ev.get("date", ""),
            "name": ev.get("shortName", ev.get("name", "")),
            "home": home_name,
            "away": away_name,
            "home_score": home_score,
            "away_score": away_score,
            "team_is_home": team_is_home,
            "completed": completed,
            "status": status_type.get("shortDetail", status_type.get("description", "")),
        })
    return games


def fetch_best_worst(
    schedule: list[dict],
    espn_id: int,
    n: int = 3,
) -> tuple[list[dict], list[dict]]:
    """
    Given a schedule (from fetch_team_schedule), return:
      (best_wins, worst_losses) — each a list of up to `n` game dicts
      enriched with 'margin' and 'result' keys.

    best_wins  = wins sorted by largest margin (most dominant victories)
    worst_losses = losses sorted by largest margin (most lopsided defeats)
    """
    wins: list[dict] = []
    losses: list[dict] = []

    for g in schedule:
        if not g.get("completed"):
            continue
        hs = g.get("home_score")
        aws = g.get("away_score")
        if hs is None or aws is None:
            continue
        try:
            home_pts = int(hs)
            away_pts = int(aws)
        except (ValueError, TypeError):
            continue

        team_is_home = g.get("team_is_home", True)
        our_score  = home_pts if team_is_home else away_pts
        opp_score  = away_pts if team_is_home else home_pts
        opp_name   = g["away"] if team_is_home else g["home"]
        margin     = our_score - opp_score
        game_copy  = dict(g, margin=margin, opp_name=opp_name,
                          our_score=our_score, opp_score=opp_score)

        if margin > 0:
            wins.append(game_copy)
        else:
            losses.append(game_copy)

    best_wins    = sorted(wins,   key=lambda g: -g["margin"])[:n]
    worst_losses = sorted(losses, key=lambda g:  g["margin"])[:n]   # most negative first
    return best_wins, worst_losses


def fetch_boxscore(event_id: str, sport_key: str = "basketball_ncaab") -> dict:
    """Return simplified box score for a completed game."""
    base = BASE_URLS.get(sport_key, BASE_URLS["basketball_ncaab"])
    d = _get(f"{base}/summary?event={event_id}")
    if not d:
        return {}

    # Athletes are in boxscore.players[], NOT boxscore.teams[].statistics
    teams_box = []
    for team_entry in d.get("boxscore", {}).get("players", []):
        team_name = team_entry.get("team", {}).get("displayName", "")
        players_rows = []
        stats_cats = team_entry.get("statistics", [])
        if stats_cats:
            cat = stats_cats[0]   # one category with all players
            labels = cat.get("labels", [])
            for p in cat.get("athletes", []):
                if p.get("didNotPlay"):
                    continue
                athlete = p.get("athlete", {})
                pos = athlete.get("position", {})
                pos_abbr = pos.get("abbreviation", "") if isinstance(pos, dict) else ""
                players_rows.append({
                    "name":     athlete.get("displayName", ""),
                    "position": pos_abbr,
                    "stats":    p.get("stats", []),
                    "labels":   labels,
                })
        teams_box.append({"team": team_name, "players": players_rows})

    # Result string from header
    result_str = ""
    for c in d.get("header", {}).get("competitions", [{}])[0].get("competitors", []):
        score = c.get("score", "")
        name  = c.get("team", {}).get("displayName", "")
        if name and score:
            result_str += f"{name} {score},  "

    return {
        "result": result_str.strip(", "),
        "teams":  teams_box,
    }


def fetch_player_stats(player_data: dict) -> dict:
    """
    Build a player info dict from already-fetched roster data.
    The individual ESPN athlete endpoint is unauthenticated-blocked,
    so we use the rich data already returned by the roster endpoint.
    """
    if not player_data:
        return {}
    pos_raw = player_data.get("position", "")
    if isinstance(pos_raw, dict):
        position = pos_raw.get("displayName", pos_raw.get("abbreviation", ""))
    else:
        position = pos_raw  # already extracted as string by fetch_team_roster

    hs_raw = player_data.get("headshot", "")
    headshot = hs_raw.get("href", "") if isinstance(hs_raw, dict) else hs_raw

    bp_raw = player_data.get("birthPlace", "")
    birthplace = bp_raw.get("city", "") if isinstance(bp_raw, dict) else bp_raw

    exp_raw = player_data.get("experience", "")
    year = exp_raw.get("displayValue", "") if isinstance(exp_raw, dict) else exp_raw

    return {
        "name":       player_data.get("displayName", player_data.get("name", "")),
        "position":   position,
        "headshot":   headshot,
        "height":     player_data.get("displayHeight", player_data.get("height", "")),
        "weight":     player_data.get("displayWeight", player_data.get("weight", "")),
        "birthPlace": birthplace,
        "year":       player_data.get("year", year),
        "jersey":     player_data.get("jersey", ""),
        "stats":      player_data.get("stats", {}),
    }



# ── Height helper ───────────────────────────────────────────────────────────────
def inches_to_ft(raw) -> str:
    """Convert raw height value (inches float/int or 'X-Y' string) to '6\'2"' format."""
    if not raw:
        return ""
    if isinstance(raw, (int, float)):
        total = int(raw)
    else:
        s = str(raw).strip()
        if "-" in s:
            try:
                ft_part, in_part = s.split("-", 1)
                return f"{int(ft_part)}'{int(in_part)}\""
            except ValueError:
                pass
        try:
            total = int(float(s))
        except ValueError:
            return s
    feet, remaining = divmod(total, 12)
    return f"{feet}'{remaining}\""


# ── Stat leaders from most recent box score ─────────────────────────────────────
def fetch_team_stat_leaders(espn_id: int, team_display_name: str = "") -> dict:
    """
    Return {pts_leader, reb_leader, ast_leader} dicts with 'name' and 'value'
    derived from the most recent completed game box score.
    """
    sched = _get(f"{BASE}/teams/{espn_id}/schedule")
    if not sched:
        return {}

    completed = [
        ev.get("id") for ev in sched.get("events", [])
        if ev.get("competitions", [{}])[0].get("status", {}).get("type", {}).get("completed")
    ]
    if not completed:
        return {}

    eid = completed[-1]
    bs = _get(f"{BASE}/summary?event={eid}")
    if not bs:
        return {}

    for team_entry in bs.get("boxscore", {}).get("players", []):
        tname = team_entry.get("team", {}).get("displayName", "")
        # Match by display name fragment
        if team_display_name and team_display_name.split()[0].lower() not in tname.lower():
            continue
        cats = team_entry.get("statistics", [{}])
        if not cats:
            continue
        labels = cats[0].get("labels", [])
        athletes = cats[0].get("athletes", [])
        try:
            pi = labels.index("PTS")
            ri = labels.index("REB")
            ai = labels.index("AST")
        except ValueError:
            return {}

        def leader(idx: int) -> dict:
            best = max(
                (a for a in athletes if not a.get("didNotPlay") and a.get("stats")),
                key=lambda a: int(a.get("stats", [])[idx]) if a.get("stats") and len(a["stats"]) > idx and str(a["stats"][idx]).isdigit() else 0,
                default=None,
            )
            if best:
                return {
                    "name":  best.get("athlete", {}).get("shortName", best.get("athlete", {}).get("displayName", "")),
                    "value": best.get("stats", [])[idx] if len(best.get("stats", [])) > idx else "—",
                }
            return {"name": "—", "value": "—"}

        return {
            "pts": leader(pi),
            "reb": leader(ri),
            "ast": leader(ai),
        }
    return {}


_ALL_TEAMS_CACHE: dict[str, dict[str, int]] = {}
_ALL_TEAMS_DISPLAY_MAP: dict[str, dict[str, int]] = {}

# Explicit disambiguation: maps how The-Odds-API names teams → canonical ESPN displayName.
# This prevents short names (e.g. "North Carolina") from matching longer ESPN names
# that contain the same words (e.g. "North Carolina Central Eagles").
_TEAM_NAME_ALIASES: dict[str, str] = {
    # ACC / ACC-adjacent blue-bloods with risky overlaps
    "north carolina":              "North Carolina Tar Heels",
    "unc":                         "North Carolina Tar Heels",
    "nc state":                    "NC State Wolfpack",
    "north carolina state":        "NC State Wolfpack",
    # Maryland overlap (Maryland-Eastern Shore)
    "maryland":                    "Maryland Terrapins",
    # Mississippi overlap (Mississippi Valley State)
    "ole miss":                    "Ole Miss Rebels",
    "mississippi":                 "Ole Miss Rebels",
    # Alabama overlap (Alabama A&M, Alabama State)
    "alabama":                     "Alabama Crimson Tide",
    # Florida overlap (Florida A&M, Florida Atlantic, etc.)
    "florida":                     "Florida Gators",
    # Texas overlap (Texas Southern, Texas State, etc.)
    "texas":                       "Texas Longhorns",
    # Oklahoma overlap (Oklahoma State)
    "oklahoma":                    "Oklahoma Sooners",
    # Georgia overlap (Georgia Southern, Georgia State, Georgia Tech)
    "georgia":                     "Georgia Bulldogs",
    # Arkansas overlap (Arkansas State, Arkansas-Pine Bluff)
    "arkansas":                    "Arkansas Razorbacks",
    # Michigan overlap (Michigan State)
    "michigan":                    "Michigan Wolverines",
    # Indiana overlap (Indiana State)
    "indiana":                     "Indiana Hoosiers",
    # Oregon overlap (Oregon State)
    "oregon":                      "Oregon Ducks",
    # Kansas overlap (Kansas City / Kansas State handled by 'kansas state' exact)
    "kansas":                      "Kansas Jayhawks",
    # Washington overlap (Washington State)
    "washington":                  "Washington Huskies",
    # Connecticut / UConn overlap
    "connecticut":                 "UConn Huskies",
    "uconn":                       "UConn Huskies",
}


def get_espn_team_id(team_name: str, sport_key: str = "basketball_ncaab") -> Optional[int]:
    """Fetch and cache all 362 Div 1 basketball teams to resolve IDs by name."""
    global _ALL_TEAMS_CACHE, _ALL_TEAMS_DISPLAY_MAP
    if sport_key not in _ALL_TEAMS_CACHE:
        _ALL_TEAMS_CACHE[sport_key] = {}
        _ALL_TEAMS_DISPLAY_MAP[sport_key] = {}
        base = BASE_URLS.get(sport_key, BASE_URLS["basketball_ncaab"])
        url = f"{base}/teams?limit=400"
        d = _get(url)
        if d:
            teams = d.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])
            for t_node in teams:
                t = t_node.get("team", {})
                tid = int(t.get("id", 0))
                if tid:
                    dn = t.get("displayName", "")
                    _ALL_TEAMS_DISPLAY_MAP[sport_key][dn] = tid
                    _ALL_TEAMS_CACHE[sport_key][dn.lower()] = tid
                    _ALL_TEAMS_CACHE[sport_key][t.get("shortDisplayName", "").lower()] = tid
                    if t.get("nickname"):
                        _ALL_TEAMS_CACHE[sport_key][t.get("nickname", "").lower()] = tid

    search = team_name.lower().strip()

    # Step 1: Check explicit disambiguation alias table first
    canonical = _TEAM_NAME_ALIASES.get(search)
    if canonical:
        # Look up canonical name in cache
        result = _ALL_TEAMS_CACHE.get(sport_key, {}).get(canonical.lower())
        if result:
            return result

    # Step 2: Exact match (after normalising "state" → "st")
    search_norm = search.replace(" state", " st").replace(" st.", " st")
    for k, v in _ALL_TEAMS_CACHE[sport_key].items():
        k_norm = k.replace(" state", " st").replace(" st.", " st")
        if search_norm == k_norm:
            return v

    import re
    # Step 3: Word-boundary fallback — but prefer the SHORTEST matching key
    # (so "Maryland" won't grab "Maryland-Eastern Shore" when "Maryland Terrapins" exists)
    candidates: list[tuple[int, str, int]] = []  # (key_len, key, team_id)
    for k, v in _ALL_TEAMS_CACHE.get(sport_key, {}).items():
        if not k:
            continue
        k_norm = k.replace(" state", " st").replace(" st.", " st")
        # The search term must appear as a complete word sequence inside k, OR k inside search
        if re.search(r'\b' + re.escape(search_norm) + r'\b', k_norm):
            candidates.append((len(k), k, v))

    if candidates:
        # Prefer the candidate whose key is closest in length to the search term
        # This ensures "Maryland Terrapins" wins over "Maryland-Eastern Shore Hawks"
        candidates.sort(key=lambda x: abs(x[0] - len(search)))
        return candidates[0][2]

    return None



# ── Venue lookup from team schedule ──────────────────────────────────────────────
def fetch_game_venue(espn_team_id: Optional[int], opponent_name: str, sport_key: str = "basketball_ncaab") -> str:
    """
    Search a team's schedule to pull the exact game venue.
    """
    if not espn_team_id:
        return ""
    base = BASE_URLS.get(sport_key, BASE_URLS["basketball_ncaab"])
    url = f"{base}/teams/{espn_team_id}/schedule"
    d = _get(url)
    if not d:
        return ""

    def _norm(n: str):
        return n.lower().replace(" state", " st").replace(" st.", " st")

    target = _norm(opponent_name)
    
    for ev in d.get("events", [])[-20:]:
        c = ev.get("competitions", [{}])[0]
        comps = c.get("competitors", [])
        if len(comps) != 2:
            continue
        
        t1 = comps[0].get("team", {}).get("displayName", "").lower()
        t2 = comps[1].get("team", {}).get("displayName", "").lower()
        t1_s = comps[0].get("team", {}).get("shortDisplayName", "").lower()
        t2_s = comps[1].get("team", {}).get("shortDisplayName", "").lower()

        if target in t1 or target in t2 or target == t1_s or target == t2_s:
            venue_d = c.get("venue") or {}
            v_str = (
                f"{venue_d.get('fullName', '')} — "
                f"{venue_d.get('address', {}).get('city', '')}"
                f"{', ' + venue_d.get('address', {}).get('state', '') if venue_d.get('address', {}).get('state') else ''}"
            ).replace(" — ", "").strip()
            if venue_d.get('fullName'):
                v_str = f"{venue_d.get('fullName')} — {venue_d.get('address',{}).get('city','')}"
            return v_str.strip(" —")
    return ""



def get_all_espn_teams(sport_key: str = "basketball_ncaab") -> dict[str, int]:
    """Return a map of Team Display Name -> ESPN ID for all Div 1 teams."""
    global _ALL_TEAMS_DISPLAY_MAP
    if sport_key not in _ALL_TEAMS_DISPLAY_MAP:
        # Just call this to populate the caches
        get_espn_team_id("Unknown", sport_key)
    return _ALL_TEAMS_DISPLAY_MAP.get(sport_key, {})


_ALL_STANDINGS_CACHE = {}

def get_all_standings(sport_key: str = "basketball_ncaab") -> dict[str, dict]:
    """
    Fetch standing info for all D1 teams.
    Returns: { "Team Name" : {"conference": "ACC", "conf_win_pct": 0.850} }
    """
    global _ALL_STANDINGS_CACHE
    if sport_key in _ALL_STANDINGS_CACHE:
        return _ALL_STANDINGS_CACHE[sport_key]
        
    base = BASE_URLS.get(sport_key, BASE_URLS["basketball_ncaab"])
    url = base.replace("/site/v2", "/v2") + "/standings"
    d = _get(url)
    if not d:
        return {}
        
    cache_dict = {}
    for conf in d.get("children", []):
        c_name = conf.get("name", "").replace(" Conference", "").replace(" Athletic", "")
        
        CONF_MAP = {
            "Atlantic Coast": "ACC",
            "Mid-Eastern": "MEAC",
            "Southeastern": "SEC",
            "Coastal Association": "CAA",
            "Conference USA": "CUSA",
            "Horizon League": "Horizon",
            "Ivy League": "Ivy",
            "Metro Atlantic": "MAAC",
            "Mid-American": "MAC",
            "Northeast": "NEC",
            "Ohio Valley": "OVC",
            "Patriot League": "Patriot",
            "Southern": "SoCon",
            "Southwestern": "SWAC",
            "Summit League": "Summit",
            "West Coast": "WCC",
            "Western": "WAC"
        }
        if c_name in CONF_MAP:
            c_name = CONF_MAP[c_name]
            
        entries = conf.get("standings", {}).get("entries", [])
        for entry in entries:
            t = entry.get("team", {})
            t_name = t.get("displayName", "")
            
            wpct = 0.0
            for stat in entry.get("stats", []):
                if stat.get("type") == "vsconf_winpercent":
                    wpct = float(stat.get("value", 0.0))
                    
            cache_dict[t_name] = {
                "conference": c_name,
                "conf_win_pct": wpct
            }
            
    _ALL_STANDINGS_CACHE[sport_key] = cache_dict
    return cache_dict

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
