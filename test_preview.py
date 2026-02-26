import asyncio
import traceback
from pydantic_ai.exceptions import UnexpectedModelBehavior
from src.tools.odds_client import get_live_games
from src.db.storage import BetLedger
from src.agents.batch_preview import generate_slate_previews

async def main():
    ledger = BetLedger()
    games = get_live_games(ledger)
    if not games:
        print("No games.")
        return
        
    print(f"Loaded {len(games)} games.")
    try:
        res = await generate_slate_previews(games[:3])
        print(res)
    except Exception as e:
        print(f"Exception: {type(e).__name__} - {e}")
        if isinstance(e, UnexpectedModelBehavior):
            print("Underlying cause:")
            print(getattr(e, '__cause__', None))
            # Some Pydantic errors have .errors()
            if hasattr(e.__cause__, 'errors'):
                print(e.__cause__.errors())

if __name__ == "__main__":
    asyncio.run(main())
