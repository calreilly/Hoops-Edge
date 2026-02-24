"""
Hoops Edge — Phase 1 CLI (Improved)
Usage:
  python -m src.main --slate              # Analyze today's mock slate
  python -m src.main --bets              # Show pending bets from DB
  python -m src.main --bankroll          # Show current bankroll
  python -m src.main --seed             # Seed team stats from JSON into DB
  python -m src.main --settle <bet_id> <result> <profit>
                                          # Settle a bet: result = win|loss|push
"""
import asyncio
import argparse

from src.agents.ev_calculator import analyze_full_slate
from src.db.storage import BetLedger
from src.tools.odds_client import get_live_games


async def run_slate(ledger: BetLedger, dry_run: bool = False):
    games = get_live_games(ledger)
    print(f"\n🏀 Analyzing {len(games)} games on today's CBB slate...\n")
    slate = await analyze_full_slate(games)

    print(f"{'─'*60}")
    print(f"  DATE: {slate.date} | GAMES: {slate.games_analyzed}")
    print(f"{'─'*60}")

    if not slate.positive_ev_bets:
        print("  ❌ No +EV bets found today. Sit on your hands.")
    else:
        print(f"  ✅ {len(slate.positive_ev_bets)} +EV bet(s) found:\n")

    for rec in slate.bets:
        marker = "✅" if rec.is_recommended else "  "
        line_str = f" {rec.line:+.1f}" if rec.line else ""
        print(
            f"  {marker} [{rec.bet_type.value.upper()}] "
            f"{rec.away_team} @ {rec.home_team} | "
            f"{rec.side.value.upper()}{line_str} @ {rec.american_odds:+d} | "
            f"EV: {rec.ev_analysis.expected_value:+.1%} | "
            f"Units: {rec.recommended_units:.2f}u (Kelly)"
        )
        print(f"     → {rec.summary}")
        if rec.is_recommended:
            print(f"     CoT reasoning ({len(rec.ev_analysis.reasoning_steps)} steps):")
            for i, step in enumerate(rec.ev_analysis.reasoning_steps, 1):
                print(f"       {i}. {step}")
        print()

        if not dry_run and rec.is_recommended:
            bet_id = ledger.save_recommendation(rec)
            print(f"     💾 Saved to DB (id={bet_id[:8]}...) — status: pending")

    print(f"{'─'*60}")
    print(f"  Total units at risk: {slate.total_units_at_risk:.2f}u")
    bankroll = ledger.get_bankroll()
    print(f"  Current bankroll: {bankroll['balance_units']:.1f}u "
          f"(${bankroll['balance_units'] * bankroll['unit_dollar_value']:.2f})")
    print(f"{'─'*60}\n")


def show_bets(ledger: BetLedger, status: str = "pending"):
    bets = list(ledger.db["bets"].rows_where("status = ?", [status]))
    if not bets:
        print(f"\n  No {status} bets.")
        return
    print(f"\n{'─'*60}")
    print(f"  {status.upper()} BETS ({len(bets)})")
    print(f"{'─'*60}")
    for b in bets:
        pl = f"  P/L: {b['profit_loss']:+.2f}u" if b.get("profit_loss") is not None else ""
        print(f"  [{b['id'][:8]}] {b['away_team']} @ {b['home_team']} | "
              f"{b['bet_type'].upper()} {b['side'].upper()} @ {b['american_odds']:+d} | "
              f"EV: {b['expected_value']:+.1%} | {b['recommended_units']:.2f}u{pl}")
        print(f"  → {b['summary']}\n")


def show_bankroll(ledger: BetLedger):
    b = ledger.get_bankroll()
    settled = list(ledger.db["bets"].rows_where("status = ?", ["settled"]))
    wins = sum(1 for x in settled if x["result"] == "win")
    losses = sum(1 for x in settled if x["result"] == "loss")
    total_pl = sum(x["profit_loss"] for x in settled if x["profit_loss"] is not None)
    print(f"\n  💰 Bankroll: {b['balance_units']:.1f}u "
          f"(${b['balance_units'] * b['unit_dollar_value']:.2f} @ "
          f"${b['unit_dollar_value']:.2f}/unit)")
    print(f"  Record: {wins}W-{losses}L | Total P/L: {total_pl:+.2f}u")
    print(f"  Last updated: {b['updated_at']}\n")


def settle_bet(ledger: BetLedger, bet_id_prefix: str, result: str, profit_loss: float):
    """Find a bet by ID prefix and settle it."""
    all_bets = list(ledger.db["bets"].rows_where("id LIKE ?", [f"{bet_id_prefix}%"]))
    if not all_bets:
        print(f"  ❌ No bet found with ID starting with '{bet_id_prefix}'")
        return
    if len(all_bets) > 1:
        print(f"  ❌ Ambiguous ID prefix — matches {len(all_bets)} bets. Be more specific.")
        return

    bet = all_bets[0]
    ledger.settle_bet(bet["id"], result, profit_loss)
    print(f"\n  ✅ Bet [{bet['id'][:8]}] settled as {result.upper()} ({profit_loss:+.2f}u)")
    show_bankroll(ledger)


def seed_teams(db_path: str = "data/hoops_edge.db"):
    """Seed team stats from data/team_stats.json into SQLite (Week 4)."""
    from src.tools.seed_teams import seed_from_json
    seed_from_json(db_path=db_path)


async def main():
    parser = argparse.ArgumentParser(description="Hoops Edge — CBB +EV Betting Agent")
    parser.add_argument("--slate", action="store_true", help="Analyze today's full slate")
    parser.add_argument("--dry-run", action="store_true", help="Don't save bets to DB")
    parser.add_argument("--bets", action="store_true", help="Show pending bets")
    parser.add_argument("--approved", action="store_true", help="Show approved bets")
    parser.add_argument("--settled", action="store_true", help="Show settled bets")
    parser.add_argument("--bankroll", action="store_true", help="Show current bankroll & record")
    parser.add_argument("--seed", action="store_true", help="Seed team stats from data/team_stats.json")
    parser.add_argument("--settle", nargs=3, metavar=("BET_ID", "RESULT", "PROFIT_LOSS"),
                        help="Settle a bet: --settle <id_prefix> <win|loss|push> <units>")
    args = parser.parse_args()

    ledger = BetLedger()

    if args.seed:
        seed_teams()
    elif args.slate:
        await run_slate(ledger, dry_run=args.dry_run)
    elif args.bets:
        show_bets(ledger, "pending")
    elif args.approved:
        show_bets(ledger, "approved")
    elif args.settled:
        show_bets(ledger, "settled")
    elif args.bankroll:
        show_bankroll(ledger)
    elif args.settle:
        bet_id, result, pl = args.settle
        if result not in ("win", "loss", "push"):
            print("  ❌ Result must be one of: win, loss, push")
        else:
            settle_bet(ledger, bet_id, result, float(pl))
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
