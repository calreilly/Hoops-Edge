from src.tools.odds_client import fetch_live_rankings
rankings = fetch_live_rankings()
for team, (rank, rec) in rankings.items():
    if "nebraska" in team or "maryland" in team:
        print(f"FOUND in rankings: {team} -> {rank}, {rec}")

print("Total rankings:", len(rankings))
