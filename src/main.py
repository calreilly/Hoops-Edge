"""
Hoops Edge — Phase 1 CLI
Usage:
  python -m src.main --slate        # Analyze today's mock slate
  python -m src.main --game <id>    # Analyze a single game
  python -m src.main --bets         # Show pending bets from DB
  python -m src.main --bankroll     # Show current bankroll
"""
import asyncio
import argparse
import json

from src.agents.ev_calculator import analyze_full_slate
from src.db.storage import BetLedger
from src.tools.mock_odds import get_mock_games


async def run_slate(ledger: BetLedger, dry_run: bool = False):
    games = get_mock_games()
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
            f"Units: {rec.recommended_units:.1f}u"
        )
        print(f"     → {rec.summary}")
        if rec.is_recommended:
            print(f"     CoT reasoning ({len(rec.ev_analysis.reasoning_steps)} steps):")
            for i, step in enumerate(rec.ev_analysis.reasoning_steps, 1):
                print(f"       {i}. {step}")
        print()

        if not dry_run:
            bet_id = ledger.save_recommendation(rec)
            if rec.is_recommended:
                print(f"     💾 Saved to DB (id={bet_id[:8]}...) — status: pending")

    print(f"{'─'*60}")
    print(f"  Total units at risk: {slate.total_units_at_risk:.1f}u")
    bankroll = ledger.get_bankroll()
    print(f"  Current bankroll: {bankroll['balance_units']:.1f}u "
          f"(${bankroll['balance_units'] * bankroll['unit_dollar_value']:.2f})")
    print(f"{'─'*60}\n")


def show_bets(ledger: BetLedger):
    bets = ledger.get_pending_bets()
    if not bets:
        print("No pending bets.")
        return
    print(f"\n{'─'*60}")
    print(f"  PENDING BETS ({len(bets)})")
    print(f"{'─'*60}")
    for b in bets:
        print(f"  [{b['id'][:8]}] {b['away_team']} @ {b['home_team']} | "
              f"{b['bet_type'].upper()} {b['side'].upper()} @ {b['american_odds']:+d} | "
              f"EV: {b['expected_value']:+.1%} | {b['recommended_units']:.1f}u")
        print(f"  → {b['summary']}\n")


def show_bankroll(ledger: BetLedger):
    b = ledger.get_bankroll()
    print(f"\n  💰 Bankroll: {b['balance_units']:.1f} units "
          f"(${b['balance_units'] * b['unit_dollar_value']:.2f} @ "
          f"${b['unit_dollar_value']:.2f}/unit)")
    print(f"  Last updated: {b['updated_at']}\n")


async def main():
    parser = argparse.ArgumentParser(description="Hoops Edge — CBB +EV Betting Agent")
    parser.add_argument("--slate", action="store_true", help="Analyze today's full slate")
    parser.add_argument("--dry-run", action="store_true", help="Don't save to DB")
    parser.add_argument("--bets", action="store_true", help="Show pending bets")
    parser.add_argument("--bankroll", action="store_true", help="Show current bankroll")
    args = parser.parse_args()

    ledger = BetLedger()

    if args.slate:
        await run_slate(ledger, dry_run=args.dry_run)
    elif args.bets:
        show_bets(ledger)
    elif args.bankroll:
        show_bankroll(ledger)
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
