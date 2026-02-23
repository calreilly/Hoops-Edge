"""
Week 4: Seed team stats from data/team_stats.json into SQLite.
Run once to populate the DB: python -m src.tools.seed_teams
"""
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.db.storage import BetLedger
from src.models.schemas import TeamStats


def seed_from_json(json_path: str = "data/team_stats.json", db_path: str = "data/hoops_edge.db"):
    ledger = BetLedger(db_path=db_path)
    path = Path(json_path)

    if not path.exists():
        print(f"Error: {json_path} not found.")
        return

    with open(path) as f:
        teams = json.load(f)

    count = 0
    for t in teams:
        stats = TeamStats(
            team_id=t["team_id"],
            team_name=t["team_name"],
            record=t["record"],
            offensive_efficiency=t.get("offensive_efficiency"),
            defensive_efficiency=t.get("defensive_efficiency"),
            pace=t.get("pace"),
            three_point_rate=t.get("three_point_rate"),
            ats_record=t.get("ats_record"),
            conference=t.get("conference"),
            last_updated=datetime.utcnow(),
        )
        ledger.upsert_team_stats(stats)
        count += 1

    print(f"✅ Seeded {count} teams into {db_path}")


if __name__ == "__main__":
    seed_from_json()
