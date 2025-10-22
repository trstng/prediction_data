"""
REST API poller for supplementing WebSocket data.
Polls Kalshi REST API at regular intervals as fallback/supplement.
"""
import asyncio
from typing import List, Set
from datetime import datetime
import structlog

from config.settings import settings
from src.database.models import MarketSnapshot, Trade, OrderbookDepth, OrderbookLevel
from src.database.writer import SupabaseWriter
from src.collectors.kalshi_auth import KalshiRestClient, KalshiAuth
from src.utils.rate_limiter import AdaptiveRateLimiter

logger = structlog.get_logger()


class RestPoller:
    """Polls Kalshi REST API for market data."""

    def __init__(self, db_writer: SupabaseWriter, rest_client: KalshiRestClient):
        """
        Initialize REST poller.

        Args:
            db_writer: SupabaseWriter instance
            rest_client: KalshiRestClient instance
        """
        self.db = db_writer
        self.client = rest_client

        self.poll_interval = settings.collection_interval_seconds
        self.rate_limiter = AdaptiveRateLimiter(
            settings.kalshi_rest_requests_per_minute,
            name="kalshi_rest"
        )

        self.active_markets: Set[str] = set()
        self.is_running = False

        logger.info(
            "rest_poller_initialized",
            poll_interval=self.poll_interval,
            rate_limit=settings.kalshi_rest_requests_per_minute
        )

    async def poll_market_snapshot(self, ticker: str) -> bool:
        """
        Poll single market and create snapshot.

        Args:
            ticker: Market ticker

        Returns:
            True if successful
        """
        await self.rate_limiter.acquire()

        try:
            market = await self.client.get_market(ticker)

            if not market:
                return False

            await self.rate_limiter.report_success()

            # Create snapshot
            now = datetime.utcnow()
            timestamp = int(now.timestamp())
            timestamp_ms = int(now.timestamp() * 1000)

            yes_bid = market.get("yes_bid")
            yes_ask = market.get("yes_ask")
            no_bid = market.get("no_bid")
            no_ask = market.get("no_ask")

            # Calculate derived metrics
            mid_price = None
            spread = None
            if yes_bid is not None and yes_ask is not None:
                mid_price = (yes_bid + yes_ask) / 2.0
                spread = yes_ask - yes_bid

            snapshot = MarketSnapshot(
                market_ticker=ticker,
                timestamp=timestamp,
                timestamp_ms=timestamp_ms,
                yes_bid=yes_bid,
                yes_ask=yes_ask,
                no_bid=no_bid,
                no_ask=no_ask,
                last_price=market.get("last_price"),
                yes_bid_size=None,  # Not always available via REST
                yes_ask_size=None,
                no_bid_size=None,
                no_ask_size=None,
                volume=market.get("volume"),
                volume_24h=market.get("volume_24h"),
                open_interest=market.get("open_interest"),
                mid_price=mid_price,
                spread=spread
            )

            await self.db.queue_snapshot(snapshot)

            logger.debug("market_polled", ticker=ticker)

            return True

        except Exception as e:
            logger.error("market_poll_failed", ticker=ticker, error=str(e))
            await self.rate_limiter.report_rate_limit_hit()
            return False

    async def poll_market_orderbook(self, ticker: str, depth: int = 10) -> bool:
        """
        Poll market orderbook.

        Args:
            ticker: Market ticker
            depth: Orderbook depth

        Returns:
            True if successful
        """
        await self.rate_limiter.acquire()

        try:
            orderbook_data = await self.client.get_orderbook(ticker, depth)

            if not orderbook_data:
                return False

            await self.rate_limiter.report_success()

            now = datetime.utcnow()
            timestamp = int(now.timestamp())

            # Process YES side
            if "yes" in orderbook_data and orderbook_data["yes"]:
                yes_levels = [
                    OrderbookLevel(price=level["price"], size=level.get("quantity", level.get("size", 0)))
                    for level in orderbook_data["yes"]
                ]

                if yes_levels:
                    yes_orderbook = OrderbookDepth(
                        market_ticker=ticker,
                        timestamp=timestamp,
                        side="yes",
                        orderbook=yes_levels
                    )
                    await self.db.insert_orderbook_depth(yes_orderbook)

            # Process NO side
            if "no" in orderbook_data and orderbook_data["no"]:
                no_levels = [
                    OrderbookLevel(price=level["price"], size=level.get("quantity", level.get("size", 0)))
                    for level in orderbook_data["no"]
                ]

                if no_levels:
                    no_orderbook = OrderbookDepth(
                        market_ticker=ticker,
                        timestamp=timestamp,
                        side="no",
                        orderbook=no_levels
                    )
                    await self.db.insert_orderbook_depth(no_orderbook)

            logger.debug("orderbook_polled", ticker=ticker, depth=depth)

            return True

        except Exception as e:
            logger.error("orderbook_poll_failed", ticker=ticker, error=str(e))
            await self.rate_limiter.report_rate_limit_hit()
            return False

    async def poll_recent_trades(self, ticker: str) -> bool:
        """
        Poll recent trades for a market.

        Args:
            ticker: Market ticker

        Returns:
            True if successful
        """
        await self.rate_limiter.acquire()

        try:
            trades_data = await self.client.get_trades(ticker=ticker, limit=50)

            if not trades_data:
                return True  # No trades is okay

            await self.rate_limiter.report_success()

            trades = []
            for trade_data in trades_data:
                # Parse timestamp if available
                timestamp = int(datetime.utcnow().timestamp())
                if "created_time" in trade_data:
                    try:
                        created_time = datetime.fromisoformat(
                            trade_data["created_time"].replace("Z", "+00:00")
                        )
                        timestamp = int(created_time.timestamp())
                    except:
                        pass

                trade = Trade(
                    market_ticker=ticker,
                    trade_id=trade_data.get("trade_id"),
                    timestamp=timestamp,
                    timestamp_ms=timestamp * 1000,
                    price=trade_data.get("price", 0),
                    size=trade_data.get("count", trade_data.get("quantity", 1)),
                    taker_side=trade_data.get("taker_side")
                )
                trades.append(trade)

            if trades:
                await self.db.insert_trades(trades)

            logger.debug("trades_polled", ticker=ticker, count=len(trades))

            return True

        except Exception as e:
            logger.error("trades_poll_failed", ticker=ticker, error=str(e))
            await self.rate_limiter.report_rate_limit_hit()
            return False

    async def poll_all_markets(self):
        """Poll all active markets."""
        if not self.active_markets:
            logger.warning("no_active_markets_to_poll")
            return

        logger.info("polling_markets", count=len(self.active_markets))

        # Poll snapshots for all markets
        tasks = [self.poll_market_snapshot(ticker) for ticker in self.active_markets]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        success_count = sum(1 for r in results if r is True)

        logger.info(
            "market_poll_completed",
            total=len(self.active_markets),
            successful=success_count
        )

    async def update_active_markets(self, tickers: List[str]):
        """
        Update the list of markets to poll.

        Args:
            tickers: List of market tickers
        """
        self.active_markets = set(tickers)
        logger.info("active_markets_updated", count=len(tickers))

    async def run_continuous(self):
        """Run continuous polling loop."""
        self.is_running = True
        logger.info("rest_poller_started", interval=self.poll_interval)

        while self.is_running:
            try:
                await self.poll_all_markets()

                # Flush queued snapshots periodically
                await self.db.flush_all_queues()

                await asyncio.sleep(self.poll_interval)

            except Exception as e:
                logger.error("polling_loop_error", error=str(e))
                await asyncio.sleep(5)

    async def stop(self):
        """Stop the poller."""
        self.is_running = False
        logger.info("rest_poller_stopped")
