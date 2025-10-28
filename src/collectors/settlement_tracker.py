"""
Settlement tracker for updating market status, results, and settlements.
Periodically checks all tracked markets and updates their settlement data.
"""
import asyncio
from typing import List, Dict, Any
from datetime import datetime, timezone
import structlog

from config.settings import settings
from src.database.models import MarketMetadata
from src.database.writer import SupabaseWriter
from src.collectors.kalshi_auth import KalshiRestClient

logger = structlog.get_logger()


class SettlementTracker:
    """Tracks and updates settlement information for markets."""

    def __init__(self, db_writer: SupabaseWriter, rest_client: KalshiRestClient):
        """
        Initialize settlement tracker.

        Args:
            db_writer: SupabaseWriter instance
            rest_client: KalshiRestClient instance
        """
        self.db = db_writer
        self.client = rest_client

        # Check for settlements every 30 minutes
        self.check_interval = 1800  # 30 minutes in seconds
        self.is_running = False

        # Track last update time per market to avoid excessive API calls
        self.last_updated: Dict[str, int] = {}

        logger.info(
            "settlement_tracker_initialized",
            check_interval=self.check_interval
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

    async def update_market_settlement(self, ticker: str) -> bool:
        """
        Update settlement information for a single market.

        Fetches current market data from Kalshi and updates:
        - status (active, closed, settled)
        - result (winner outcome)
        - settlement_value
        - close_time (if changed)

        Args:
            ticker: Market ticker

        Returns:
            True if updated successfully
        """
        try:
            # Fetch latest market data from Kalshi
            market_data = await self.client.get_market(ticker)

            if not market_data:
                logger.warning("market_not_found", ticker=ticker)
                return False

            # Get current metadata from database
            current_market = await self.db.get_market_by_ticker(ticker)
            if not current_market:
                logger.warning("market_not_in_db", ticker=ticker)
                return False

            # Check if status changed
            old_status = current_market.get("status")
            new_status = market_data.get("status", "active")

            # Create updated metadata
            metadata = MarketMetadata(
                market_ticker=ticker,
                event_ticker=market_data.get("event_ticker", current_market.get("event_ticker", "")),
                series_ticker=current_market.get("series_ticker"),  # Keep our series mapping
                title=market_data.get("title", current_market.get("title", "")),
                subtitle=market_data.get("subtitle", current_market.get("subtitle")),
                market_type=market_data.get("market_type", current_market.get("market_type")),
                category=market_data.get("category", current_market.get("category")),
                open_time=self._parse_timestamp(market_data.get("open_time", "")),
                close_time=self._parse_timestamp(market_data.get("close_time", "")),
                expected_expiration_time=self._parse_timestamp(
                    market_data.get("expected_expiration_time", "")
                ),
                status=new_status,
                volume_24h=market_data.get("volume_24h", 0),
                liquidity=market_data.get("liquidity"),
                can_close_early=market_data.get("can_close_early", False),
                expiration_value=market_data.get("expiration_value"),
                open_interest=market_data.get("open_interest", 0),
                result=market_data.get("result"),  # Settlement result
                settlement_value=market_data.get("settlement_value")  # Settlement value
            )

            # Update in database (upsert will handle it)
            success = await self.db.insert_market_metadata(metadata)

            if success and old_status != new_status:
                logger.info(
                    "market_status_updated",
                    ticker=ticker,
                    old_status=old_status,
                    new_status=new_status,
                    result=metadata.result,
                    settlement_value=metadata.settlement_value
                )

            # Track last update time
            self.last_updated[ticker] = int(datetime.now(timezone.utc).timestamp())

            return success

        except Exception as e:
            logger.error(
                "settlement_update_failed",
                ticker=ticker,
                error=str(e)
            )
            return False

    async def get_markets_needing_update(self) -> List[Dict[str, Any]]:
        """
        Get list of markets that need settlement updates.

        Prioritizes:
        1. Markets past their expected expiration time
        2. Markets that haven't been checked recently
        3. Active markets (since settled ones rarely change)

        Returns:
            List of market metadata dicts
        """
        try:
            # Get all tracked markets
            all_markets = []

            # Get active markets (highest priority)
            active_markets = await self.db.get_active_markets()
            all_markets.extend(active_markets)

            # Also check closed markets (they might settle)
            # Note: We'd need to add a get_markets_by_status method or modify the query
            # For now, focusing on active markets

            now_ts = int(datetime.now(timezone.utc).timestamp())
            needs_update = []

            for market in all_markets:
                ticker = market.get("market_ticker")
                expected_exp = market.get("expected_expiration_time", 0)
                status = market.get("status", "active")

                # Skip if recently updated (within last 10 minutes)
                last_update = self.last_updated.get(ticker, 0)
                if now_ts - last_update < 600:  # 10 minutes
                    continue

                # Priority 1: Games past expected expiration
                if expected_exp > 0 and expected_exp < now_ts and status == "active":
                    needs_update.append(market)
                    continue

                # Priority 2: Active markets not checked in last 30 minutes
                if status == "active" and (now_ts - last_update > 1800):
                    needs_update.append(market)
                    continue

            logger.info(
                "markets_needing_update",
                total=len(all_markets),
                needs_update=len(needs_update)
            )

            return needs_update

        except Exception as e:
            logger.error("get_markets_needing_update_failed", error=str(e))
            return []

    async def update_all_settlements(self) -> Dict[str, int]:
        """
        Update settlements for all markets needing updates.

        Returns:
            Dict with update statistics
        """
        markets = await self.get_markets_needing_update()

        stats = {
            "total": len(markets),
            "updated": 0,
            "failed": 0,
            "status_changed": 0
        }

        if not markets:
            logger.info("no_markets_need_update")
            return stats

        logger.info("starting_settlement_updates", count=len(markets))

        # Update markets in small batches to avoid rate limits
        batch_size = 10
        for i in range(0, len(markets), batch_size):
            batch = markets[i:i + batch_size]

            # Update each market in the batch
            for market in batch:
                ticker = market.get("market_ticker")
                old_status = market.get("status")

                success = await self.update_market_settlement(ticker)

                if success:
                    stats["updated"] += 1

                    # Check if status actually changed
                    updated_market = await self.db.get_market_by_ticker(ticker)
                    if updated_market and updated_market.get("status") != old_status:
                        stats["status_changed"] += 1
                else:
                    stats["failed"] += 1

                # Small delay between updates
                await asyncio.sleep(0.5)

            # Delay between batches
            await asyncio.sleep(2)

        logger.info(
            "settlement_updates_completed",
            **stats
        )

        return stats

    async def run_continuous_tracking(self):
        """Run continuous settlement tracking loop."""
        self.is_running = True
        logger.info("settlement_tracking_started", interval=self.check_interval)

        # Do an initial update right away
        await self.update_all_settlements()

        while self.is_running:
            try:
                # Wait for check interval
                await asyncio.sleep(self.check_interval)

                # Update settlements
                await self.update_all_settlements()

            except Exception as e:
                logger.error("settlement_tracking_loop_error", error=str(e))
                await asyncio.sleep(60)  # Wait 1 minute before retrying

    async def stop(self):
        """Stop settlement tracking."""
        self.is_running = False
        logger.info("settlement_tracker_stopped")
