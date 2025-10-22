"""
Market discovery system for finding and tracking sports markets.
"""
import asyncio
from typing import List, Set
from datetime import datetime
import structlog

from config.settings import settings
from src.database.models import MarketMetadata, KalshiMarket
from src.database.writer import SupabaseWriter
from src.collectors.kalshi_auth import KalshiRestClient

logger = structlog.get_logger()


class MarketFinder:
    """Discovers and tracks sports markets."""

    def __init__(self, db_writer: SupabaseWriter, rest_client: KalshiRestClient):
        """
        Initialize market finder.

        Args:
            db_writer: SupabaseWriter instance
            rest_client: KalshiRestClient instance
        """
        self.db = db_writer
        self.client = rest_client

        self.target_sports = settings.target_sports_list
        self.discovered_markets: Set[str] = set()

        self.discovery_interval = 300  # 5 minutes
        self.is_running = False

        logger.info(
            "market_finder_initialized",
            target_sports=self.target_sports,
            interval=self.discovery_interval
        )

    def _parse_timestamp(self, timestamp_str: str) -> int:
        """
        Parse ISO timestamp string to Unix timestamp.

        Args:
            timestamp_str: ISO format timestamp

        Returns:
            Unix timestamp in seconds
        """
        try:
            if not timestamp_str:
                return 0

            # Handle various ISO formats
            dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            return int(dt.timestamp())

        except Exception as e:
            logger.warning("timestamp_parse_failed", timestamp=timestamp_str, error=str(e))
            return 0

    async def discover_markets_for_series(self, series: str) -> List[MarketMetadata]:
        """
        Discover markets for a specific series using the proper series_ticker approach.

        For individual game winner markets, we need to:
        1. Use the correct series_ticker (e.g., KXNFLGAME, KXNCAAFGAME)
        2. Get events for that series
        3. Get markets for each event

        Args:
            series: Series name (e.g., "NFL", "NHL", "NBA", "CFB")

        Returns:
            List of discovered market metadata
        """
        try:
            # Map our series names to actual Kalshi series tickers for game winner markets
            series_ticker_map = {
                "NFL": "KXNFLGAME",      # Individual NFL game winners
                "NHL": "KXNHLGAME",      # Individual NHL game winners
                "NBA": "KXNBAGAME",      # Individual NBA game winners
                "CFB": "KXNCAAFGAME"     # Individual CFB game winners
            }

            series_ticker = series_ticker_map.get(series)
            if not series_ticker:
                logger.warning("unknown_series", series=series)
                return []

            logger.info(f"Discovering markets for series_ticker={series_ticker}")

            # Use the proper series_ticker parameter to get game winner markets
            markets_data = await self.client.get_markets(
                series_ticker=series_ticker,
                status="open",
                limit=1000
            )

            logger.info(f"Found {len(markets_data)} {series} markets from series {series_ticker}")

            discovered = []

            for market_data in markets_data:
                ticker = market_data.get("ticker")
                if not ticker:
                    continue

                # Create metadata
                metadata = MarketMetadata(
                    market_ticker=ticker,
                    event_ticker=market_data.get("event_ticker", ""),
                    series_ticker=series,
                    title=market_data.get("title", ""),
                    subtitle=market_data.get("subtitle"),
                    market_type=market_data.get("market_type"),
                    category=market_data.get("category"),
                    open_time=self._parse_timestamp(market_data.get("open_time", "")),
                    close_time=self._parse_timestamp(market_data.get("close_time", "")),
                    expected_expiration_time=self._parse_timestamp(
                        market_data.get("expected_expiration_time", "")
                    ),
                    status=market_data.get("status", "active"),
                    volume_24h=market_data.get("volume_24h", 0),
                    liquidity=market_data.get("liquidity"),
                    can_close_early=market_data.get("can_close_early", False),
                    expiration_value=market_data.get("expiration_value"),
                    open_interest=market_data.get("open_interest", 0)
                )

                discovered.append(metadata)

                # Track as discovered
                self.discovered_markets.add(ticker)

            logger.info(
                "markets_discovered",
                series=series,
                count=len(discovered)
            )

            return discovered

        except Exception as e:
            logger.error(
                "market_discovery_failed",
                series=series,
                error=str(e)
            )
            return []

    async def discover_all_markets(self) -> List[MarketMetadata]:
        """
        Discover markets for all target sports.

        Returns:
            List of all discovered markets
        """
        all_markets = []

        for series in self.target_sports:
            markets = await self.discover_markets_for_series(series)
            all_markets.extend(markets)

            # Small delay between series
            await asyncio.sleep(1)

        logger.info(
            "discovery_completed",
            total_markets=len(all_markets),
            sports=self.target_sports
        )

        return all_markets

    async def save_discovered_markets(self, markets: List[MarketMetadata]) -> int:
        """
        Save discovered markets to database.

        Args:
            markets: List of market metadata

        Returns:
            Number of markets saved
        """
        saved = 0

        for market in markets:
            success = await self.db.insert_market_metadata(market)
            if success:
                saved += 1

        logger.info("markets_saved", count=saved, total=len(markets))

        return saved

    async def update_market_status(self, ticker: str, status: str) -> bool:
        """
        Update market status.

        Args:
            ticker: Market ticker
            status: New status

        Returns:
            True if updated successfully
        """
        try:
            # Get current market data
            market_data = await self.client.get_market(ticker)

            if not market_data:
                return False

            # Update metadata
            metadata = MarketMetadata(
                market_ticker=ticker,
                event_ticker=market_data.get("event_ticker", ""),
                series_ticker=market_data.get("series_ticker"),
                title=market_data.get("title", ""),
                subtitle=market_data.get("subtitle"),
                market_type=market_data.get("market_type"),
                category=market_data.get("category"),
                open_time=self._parse_timestamp(market_data.get("open_time", "")),
                close_time=self._parse_timestamp(market_data.get("close_time", "")),
                expected_expiration_time=self._parse_timestamp(
                    market_data.get("expected_expiration_time", "")
                ),
                status=market_data.get("status", status),
                volume_24h=market_data.get("volume_24h", 0),
                liquidity=market_data.get("liquidity"),
                can_close_early=market_data.get("can_close_early", False),
                expiration_value=market_data.get("expiration_value"),
                open_interest=market_data.get("open_interest", 0),
                result=market_data.get("result"),
                settlement_value=market_data.get("settlement_value")
            )

            return await self.db.insert_market_metadata(metadata)

        except Exception as e:
            logger.error(
                "market_status_update_failed",
                ticker=ticker,
                error=str(e)
            )
            return False

    async def get_active_market_tickers(self) -> List[str]:
        """
        Get list of active market tickers.

        Returns:
            List of active market tickers
        """
        active_markets = await self.db.get_active_markets()
        return [m["market_ticker"] for m in active_markets]

    async def run_continuous_discovery(self):
        """Run continuous market discovery."""
        self.is_running = True
        logger.info("continuous_discovery_started", interval=self.discovery_interval)

        while self.is_running:
            try:
                # Discover markets
                markets = await self.discover_all_markets()

                # Save to database
                await self.save_discovered_markets(markets)

                # Wait before next discovery
                await asyncio.sleep(self.discovery_interval)

            except Exception as e:
                logger.error("discovery_loop_error", error=str(e))
                await asyncio.sleep(60)

    async def stop(self):
        """Stop continuous discovery."""
        self.is_running = False
        logger.info("market_finder_stopped")
