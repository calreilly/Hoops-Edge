import requests

def get_espn_records():
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"
    try:
        data = requests.get(url, timeout=5).json()
        events = data.get("events", [])
        print(f"Total events found: {len(events)}")
        for e in events[:5]:
            for c in e.get("competitions", []):
                for t in c.get("competitors", []):
                    team = t.get("team", {})
                    records = t.get("records", [])
                    print(records)
                    
                    overall = "0-0"
                    if records:
                        for r in records:
                            if r.get("type", "") == "summary" or r.get("name") == "overall" or r.get("type") == "total":
                                overall = r.get("summary", "0-0")
                                
                    print(f"Team: {team.get('name', '')}, Loc: {team.get('location', '')}, Record: {overall}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_espn_records()
