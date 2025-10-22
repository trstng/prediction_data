"""
Standalone script to explore and backfill historical data from PolyRouter.
Run this LOCALLY to understand what data is available before deciding what to backfill.

Usage:
    # Explore what's available for a specific market
    python explore_historical.py explore KXNFLGAME-25NOV02SEAWAS-WAS

    # Backfill specific markets
    python explore_historical.py backfill KXNFLGAME-25NOV02SEAWAS-WAS KXNHLGAME-25OCT24CGYWPG-WPG

    # Backfill all active markets (use with caution - respects rate limits)
    python explore_historical.py backfill-all --days 30
"""
import asyncio
import sys
from typing import List
from datetime import datetime, timedelta
import structlog

from config.settings import settings
from src.utils.logger import setup_logging
from src.database.writer import SupabaseWriter
from src.collectors.historical import HistoricalDataCollector
from src.collectors.kalshi_auth import KalshiAuth, KalshiRestClient
from src.discovery.market_finder import MarketFinder

logger = structlog.get_logger()


async def explore_market(market_ticker: str, days_back: int = 30):
    """
    Explore what historical data is available for a market.

    Args:
        market_ticker: Market ticker to explore
        days_back: How many days back to look
    """
    db_writer = SupabaseWriter()
    collector = HistoricalDataCollector(db_writer)

    print(f"\n{'='*60}")
    print(f"Exploring historical data for: {market_ticker}")
    print(f"Looking back: {days_back} days")
    print(f"{'='*60}\n")

    end_ts = int(datetime.utcnow().timestamp())
    start_ts = end_ts - (days_back * 24 * 60 * 60)

    # Try different intervals
    intervals = ["1h", "4h", "1d"]

    for interval in intervals:
        print(f"\nFetching {interval} data...")

        price_data = await collector.fetch_price_history(
            market_ids=[market_ticker],
            start_ts=start_ts,
            end_ts=end_ts,
            interval=interval
        )

        if price_data:
            print(f"  ✓ Found {len(price_data)} data points")
            print(f"  First point: {price_data[0]}")
            print(f"  Last point: {price_data[-1]}")
        else:
            print(f"  ✗ No data available for {interval} interval")

    await collector.close()
    await db_writer.close()

    print(f"\n{'='*60}")
    print("Exploration complete!")
    print(f"{'='*60}\n")


async def backfill_markets(market_tickers: List[str], days_back: int = 30):
    """
    Backfill historical data for specific markets.

    Args:
        market_tickers: List of market tickers to backfill
        days_back: How many days back to backfill
    """
    db_writer = SupabaseWriter()
    collector = HistoricalDataCollector(db_writer)

    print(f"\n{'='*60}")
    print(f"Starting backfill for {len(market_tickers)} markets")
    print(f"Days back: {days_back}")
    print(f"{'='*60}\n")

    total_inserted = await collector.backfill_markets(
        market_tickers,
        days_back=days_back,
        batch_size=5
    )

    await collector.close()
    await db_writer.close()

    print(f"\n{'='*60}")
    print(f"Backfill complete!")
    print(f"Total data points inserted: {total_inserted}")
    print(f"{'='*60}\n")


async def backfill_all_active(days_back: int = 30):
    """
    Backfill all currently active markets.

    Args:
        days_back: How many days back to backfill
    """
    db_writer = SupabaseWriter()
    auth = KalshiAuth()
    rest_client = KalshiRestClient(auth)

    # Authenticate
    await auth.login()

    # Get all active markets
    finder = MarketFinder(db_writer, rest_client)
    markets = await finder.discover_all_markets()

    if not markets:
        print("No active markets found!")
        return

    print(f"\nFound {len(markets)} active markets")
    print(f"About to backfill {days_back} days of history for each market")
    print(f"This will make approximately {len(markets) * 2} API calls to PolyRouter")
    print(f"At 10 requests/minute, this will take about {(len(markets) * 2) / 10:.1f} minutes")

    confirm = input("\nContinue? (yes/no): ")

    if confirm.lower() != 'yes':
        print("Cancelled.")
        await auth.close()
        await rest_client.close()
        await db_writer.close()
        return

    # Backfill
    market_tickers = [m.market_ticker for m in markets]
    await backfill_markets(market_tickers, days_back)

    await auth.close()
    await rest_client.close()
    await db_writer.close()


def print_usage():
    """Print usage information."""
    print(__doc__)


async def main():
    """Main entry point."""
    setup_logging()

    if len(sys.argv) < 2:
        print_usage()
        return

    command = sys.argv[1]

    try:
        if command == "explore":
            if len(sys.argv) < 3:
                print("Error: Market ticker required")
                print("Usage: python explore_historical.py explore MARKET_TICKER")
                return

            market_ticker = sys.argv[2]
            days = int(sys.argv[3]) if len(sys.argv) > 3 else 30
            await explore_market(market_ticker, days)

        elif command == "backfill":
            if len(sys.argv) < 3:
                print("Error: At least one market ticker required")
                print("Usage: python explore_historical.py backfill TICKER1 TICKER2 ...")
                return

            market_tickers = sys.argv[2:]
            await backfill_markets(market_tickers)

        elif command == "backfill-all":
            days = 30
            for arg in sys.argv[2:]:
                if arg.startswith("--days"):
                    days = int(arg.split("=")[1])

            await backfill_all_active(days)

        else:
            print(f"Unknown command: {command}")
            print_usage()

    except Exception as e:
        logger.error("script_failed", error=str(e))
        raise


if __name__ == "__main__":
    asyncio.run(main())
