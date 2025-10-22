"""
PolyRouter historical data collector.
Fetches historical market data with rate limiting.
"""
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import httpx
import structlog

from config.settings import settings
from src.database.models import HistoricalPrice
from src.database.writer import SupabaseWriter
from src.utils.rate_limiter import RateLimiter

logger = structlog.get_logger()


class HistoricalDataCollector:
    """Collects historical data from PolyRouter API."""

    def __init__(self, db_writer: SupabaseWriter):
        """
        Initialize historical data collector.

        Args:
            db_writer: SupabaseWriter instance
        """
        self.db = db_writer
        self.base_url = settings.polyrouter_base_url
        self.api_key = settings.polyrouter_api_key
        self.rate_limiter = RateLimiter(
            settings.polyrouter_requests_per_minute,
            name="polyrouter"
        )

        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={"X-API-Key": self.api_key}
        )

        logger.info(
            "historical_collector_initialized",
            base_url=self.base_url,
            rate_limit=settings.polyrouter_requests_per_minute
        )

    async def fetch_price_history(
        self,
        market_ids: List[str],
        start_ts: int,
        end_ts: int,
        interval: str = "1h",
        limit: int = 5000
    ) -> List[Dict[str, Any]]:
        """
        Fetch price history from PolyRouter API.

        Args:
            market_ids: List of Kalshi market tickers
            start_ts: Start timestamp (Unix seconds)
            end_ts: End timestamp (Unix seconds)
            interval: Data interval (1m, 5m, 1h, 4h, 1d)
            limit: Max data points per market (1-5000)

        Returns:
            List of price history data points
        """
        # Rate limit
        await self.rate_limiter.acquire()

        params = {
            "market_ids": ",".join(market_ids),
            "start_ts": start_ts,
            "end_ts": end_ts,
            "interval": interval,
            "limit": min(limit, 5000)
        }

        try:
            response = await self.client.get(
                f"{self.base_url}/price-history",
                params=params
            )
            response.raise_for_status()

            data = response.json()

            logger.info(
                "price_history_fetched",
                markets=len(market_ids),
                interval=interval,
                data_points=len(data.get("data", [])),
                from_cache=data.get("metadata", {}).get("from_cache", False)
            )

            return data.get("data", [])

        except httpx.HTTPStatusError as e:
            logger.error(
                "price_history_fetch_failed",
                status_code=e.response.status_code,
                error=str(e),
                markets=market_ids
            )
            return []

        except Exception as e:
            logger.error(
                "price_history_fetch_error",
                error=str(e),
                markets=market_ids
            )
            return []

    async def backfill_market(
        self,
        market_ticker: str,
        days_back: int = 30,
        intervals: List[str] = ["1h", "1d"]
    ) -> int:
        """
        Backfill historical data for a single market.

        Args:
            market_ticker: Kalshi market ticker
            days_back: How many days of history to fetch
            intervals: List of intervals to fetch

        Returns:
            Number of data points inserted
        """
        end_ts = int(datetime.utcnow().timestamp())
        start_ts = end_ts - (days_back * 24 * 60 * 60)

        total_inserted = 0

        for interval in intervals:
            try:
                # Fetch data
                price_data = await self.fetch_price_history(
                    market_ids=[market_ticker],
                    start_ts=start_ts,
                    end_ts=end_ts,
                    interval=interval
                )

                if not price_data:
                    logger.warning(
                        "no_historical_data",
                        market=market_ticker,
                        interval=interval
                    )
                    continue

                # Convert to HistoricalPrice models
                historical_prices = []
                for point in price_data:
                    try:
                        # Extract market ticker from point
                        ticker = point.get("market_id") or market_ticker

                        price = HistoricalPrice(
                            market_ticker=ticker,
                            platform="kalshi",
                            timestamp=point["timestamp"],
                            interval=interval,
                            open=point.get("open"),
                            high=point.get("high"),
                            low=point.get("low"),
                            close=point["close"],
                            volume=point.get("volume"),
                            open_interest=point.get("open_interest"),
                            bid_open=point.get("bid_open"),
                            bid_high=point.get("bid_high"),
                            bid_low=point.get("bid_low"),
                            bid_close=point.get("bid_close"),
                            ask_open=point.get("ask_open"),
                            ask_high=point.get("ask_high"),
                            ask_low=point.get("ask_low"),
                            ask_close=point.get("ask_close"),
                            source="polyrouter"
                        )
                        historical_prices.append(price)

                    except Exception as e:
                        logger.warning(
                            "price_point_parse_failed",
                            error=str(e),
                            point=point
                        )
                        continue

                # Insert to database
                if historical_prices:
                    success = await self.db.insert_historical_prices(historical_prices)
                    if success:
                        total_inserted += len(historical_prices)

                        logger.info(
                            "historical_data_backfilled",
                            market=market_ticker,
                            interval=interval,
                            count=len(historical_prices)
                        )

            except Exception as e:
                logger.error(
                    "backfill_interval_failed",
                    market=market_ticker,
                    interval=interval,
                    error=str(e)
                )

        return total_inserted

    async def backfill_markets(
        self,
        market_tickers: List[str],
        days_back: int = 30,
        batch_size: int = 5
    ) -> int:
        """
        Backfill multiple markets, batching to respect rate limits.

        Args:
            market_tickers: List of market tickers to backfill
            days_back: Days of history to fetch
            batch_size: Markets to process in parallel

        Returns:
            Total number of data points inserted
        """
        logger.info(
            "starting_backfill",
            total_markets=len(market_tickers),
            days_back=days_back,
            batch_size=batch_size
        )

        total_inserted = 0

        # Process in batches
        for i in range(0, len(market_tickers), batch_size):
            batch = market_tickers[i:i + batch_size]

            tasks = [
                self.backfill_market(ticker, days_back)
                for ticker in batch
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for ticker, result in zip(batch, results):
                if isinstance(result, Exception):
                    logger.error(
                        "backfill_market_failed",
                        market=ticker,
                        error=str(result)
                    )
                else:
                    total_inserted += result

            logger.info(
                "backfill_batch_completed",
                batch=f"{i + 1}-{min(i + batch_size, len(market_tickers))}",
                total=len(market_tickers)
            )

        logger.info(
            "backfill_completed",
            total_markets=len(market_tickers),
            total_data_points=total_inserted
        )

        return total_inserted

    async def backfill_all_available_history(
        self,
        market_tickers: List[str],
        batch_size: int = 5
    ) -> int:
        """
        One-time backfill of ALL available historical data from PolyRouter.
        Fetches maximum available history (up to 365 days) for each market.
        After this runs once, live streaming handles all future data.

        Args:
            market_tickers: List of market tickers to backfill
            batch_size: Markets to process in parallel

        Returns:
            Total number of data points inserted
        """
        logger.info(
            "starting_full_historical_backfill",
            total_markets=len(market_tickers),
            max_days=365
        )

        # Fetch maximum available history (365 days)
        total_inserted = await self.backfill_markets(
            market_tickers,
            days_back=365,
            batch_size=batch_size
        )

        logger.info(
            "full_historical_backfill_completed",
            total_markets=len(market_tickers),
            total_data_points=total_inserted
        )

        return total_inserted

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
        logger.info("historical_collector_closed")
