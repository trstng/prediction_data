"""
Supabase writer module for efficient database operations.
"""
import asyncio
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
import structlog
from datetime import datetime

from config.settings import settings
from .models import (
    MarketMetadata,
    MarketSnapshot,
    OrderbookDepth,
    Trade,
    HistoricalPrice,
    DataCollectionLog,
    CollectionHealth,
)

logger = structlog.get_logger()


class SupabaseWriter:
    """Handles all Supabase database operations with batching and error handling."""

    def __init__(self):
        """Initialize Supabase client."""
        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_key
        )
        self.batch_size = settings.batch_insert_size

        # Batching queues
        self._snapshot_queue: List[Dict[str, Any]] = []
        self._trade_queue: List[Dict[str, Any]] = []
        self._orderbook_queue: List[Dict[str, Any]] = []
        self._log_queue: List[Dict[str, Any]] = []

        self._lock = asyncio.Lock()

        logger.info("supabase_writer_initialized", batch_size=self.batch_size)

    async def insert_market_metadata(self, metadata: MarketMetadata) -> bool:
        """
        Insert or update market metadata.
        Uses upsert to handle updates to existing markets.
        """
        try:
            data = metadata.model_dump(exclude_none=False)
            data["updated_at"] = datetime.utcnow().isoformat()

            result = self.client.table("market_metadata").upsert(
                data,
                on_conflict="market_ticker"
            ).execute()

            logger.debug(
                "market_metadata_inserted",
                ticker=metadata.market_ticker,
                status=metadata.status
            )
            return True

        except Exception as e:
            logger.error(
                "market_metadata_insert_failed",
                error=str(e),
                ticker=metadata.market_ticker
            )
            return False

    async def insert_market_snapshots(self, snapshots: List[MarketSnapshot]) -> bool:
        """Insert market snapshots in batch."""
        if not snapshots:
            return True

        try:
            data = [s.model_dump(exclude_none=False) for s in snapshots]

            result = self.client.table("market_snapshots").insert(data).execute()

            logger.info(
                "market_snapshots_inserted",
                count=len(snapshots),
                tickers=list(set(s.market_ticker for s in snapshots))
            )
            return True

        except Exception as e:
            logger.error(
                "market_snapshots_insert_failed",
                error=str(e),
                count=len(snapshots)
            )
            return False

    async def queue_snapshot(self, snapshot: MarketSnapshot):
        """Add snapshot to queue and flush if batch size reached."""
        async with self._lock:
            self._snapshot_queue.append(snapshot.model_dump(exclude_none=False))

            if len(self._snapshot_queue) >= self.batch_size:
                await self._flush_snapshots()

    async def _flush_snapshots(self):
        """Flush snapshot queue to database."""
        if not self._snapshot_queue:
            return

        try:
            self.client.table("market_snapshots").insert(self._snapshot_queue).execute()
            count = len(self._snapshot_queue)
            self._snapshot_queue.clear()

            logger.debug("snapshot_queue_flushed", count=count)

        except Exception as e:
            logger.error("snapshot_queue_flush_failed", error=str(e))
            self._snapshot_queue.clear()

    async def insert_trades(self, trades: List[Trade]) -> bool:
        """Insert trades in batch."""
        if not trades:
            return True

        try:
            data = [t.model_dump(exclude_none=False) for t in trades]

            result = self.client.table("trades").insert(data).execute()

            logger.info(
                "trades_inserted",
                count=len(trades)
            )
            return True

        except Exception as e:
            logger.error(
                "trades_insert_failed",
                error=str(e),
                count=len(trades)
            )
            return False

    async def insert_orderbook_depth(self, orderbook: OrderbookDepth) -> bool:
        """Insert orderbook depth snapshot."""
        try:
            data = orderbook.model_dump(exclude_none=False)
            # Convert orderbook list to JSONB
            data["orderbook"] = [level.model_dump() for level in orderbook.orderbook]

            result = self.client.table("orderbook_depth").insert(data).execute()

            logger.debug(
                "orderbook_depth_inserted",
                ticker=orderbook.market_ticker,
                side=orderbook.side,
                levels=len(orderbook.orderbook)
            )
            return True

        except Exception as e:
            logger.error(
                "orderbook_depth_insert_failed",
                error=str(e),
                ticker=orderbook.market_ticker
            )
            return False

    async def insert_historical_prices(self, prices: List[HistoricalPrice]) -> bool:
        """Insert historical price data in batch."""
        if not prices:
            return True

        try:
            data = [p.model_dump(exclude_none=False) for p in prices]

            # Use upsert to avoid duplicates
            result = self.client.table("historical_prices").upsert(
                data,
                on_conflict="market_ticker,timestamp,interval"
            ).execute()

            logger.info(
                "historical_prices_inserted",
                count=len(prices)
            )
            return True

        except Exception as e:
            logger.error(
                "historical_prices_insert_failed",
                error=str(e),
                count=len(prices)
            )
            return False

    async def log(
        self,
        level: str,
        component: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        error_trace: Optional[str] = None
    ):
        """Log an event to the database."""
        try:
            log = DataCollectionLog(
                timestamp=int(datetime.utcnow().timestamp()),
                log_level=level,
                component=component,
                message=message,
                details=details,
                error_trace=error_trace
            )

            data = log.model_dump(exclude_none=False)
            self.client.table("data_collection_logs").insert(data).execute()

        except Exception as e:
            # Don't let logging failures crash the app
            logger.error("database_log_failed", error=str(e))

    async def insert_health_metric(self, health: CollectionHealth) -> bool:
        """Insert health monitoring metric."""
        try:
            data = health.model_dump(exclude_none=False)

            result = self.client.table("collection_health").insert(data).execute()

            logger.debug(
                "health_metric_inserted",
                component=health.component,
                is_healthy=health.is_healthy
            )
            return True

        except Exception as e:
            logger.error(
                "health_metric_insert_failed",
                error=str(e),
                component=health.component
            )
            return False

    async def get_active_markets(self, series: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get active markets from database."""
        try:
            query = self.client.table("market_metadata").select("*").eq("status", "active")

            if series:
                query = query.eq("series_ticker", series)

            result = query.execute()

            return result.data if result.data else []

        except Exception as e:
            logger.error("get_active_markets_failed", error=str(e), series=series)
            return []

    async def get_market_by_ticker(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get market metadata by ticker."""
        try:
            result = self.client.table("market_metadata").select("*").eq(
                "market_ticker", ticker
            ).execute()

            if result.data and len(result.data) > 0:
                return result.data[0]
            return None

        except Exception as e:
            logger.error("get_market_by_ticker_failed", error=str(e), ticker=ticker)
            return None

    async def flush_all_queues(self):
        """Flush all batched queues to database."""
        async with self._lock:
            await self._flush_snapshots()
            # Add other queue flushes as needed

        logger.info("all_queues_flushed")

    async def close(self):
        """Close connections and flush remaining data."""
        await self.flush_all_queues()
        logger.info("supabase_writer_closed")
