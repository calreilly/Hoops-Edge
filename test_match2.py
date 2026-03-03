import json

with open("data/team_stats.json") as f:
    stats = json.load(f)

for s in stats[:10]:
    print(s["team_name"])
