"""
Kalshi WebSocket live data streamer.
Real-time market data collection via WebSocket API.
"""
import asyncio
import json
from typing import Set, Dict, Any, Optional
from datetime import datetime
import websockets
from websockets.client import WebSocketClientProtocol
import structlog

from config.settings import settings
from src.database.models import MarketSnapshot, Trade, OrderbookDepth, OrderbookLevel
from src.database.writer import SupabaseWriter
from src.collectors.kalshi_auth import KalshiAuth

logger = structlog.get_logger()


class LiveStreamCollector:
    """Collects real-time market data via Kalshi WebSocket API."""

    def __init__(self, db_writer: SupabaseWriter, auth: KalshiAuth):
        """
        Initialize live stream collector.

        Args:
            db_writer: SupabaseWriter instance
            auth: KalshiAuth instance
        """
        self.db = db_writer
        self.auth = auth

        # WebSocket URL (update based on Kalshi docs)
        self.ws_url = settings.kalshi_base_url.replace("https://", "wss://").replace(
            "/trade-api/v2", "/trade-api/ws/v2"
        )

        self.websocket: Optional[WebSocketClientProtocol] = None
        self.is_connected = False
        self.subscribed_markets: Set[str] = set()

        self.reconnect_delay = settings.ws_reconnect_delay_seconds
        self.max_reconnect_attempts = settings.ws_max_reconnect_attempts
        self.ping_interval = settings.ws_ping_interval_seconds

        logger.info(
            "live_stream_initialized",
            ws_url=self.ws_url,
            reconnect_delay=self.reconnect_delay
        )

    async def connect(self) -> bool:
        """
        Connect to Kalshi WebSocket.

        Returns:
            True if connected successfully
        """
        # Ensure we have auth token
        await self.auth.ensure_authenticated()

        try:
            # Get signed headers for WebSocket connection
            # WebSocket path is /trade-api/ws/v2
            extra_headers = self.auth.get_signed_headers("GET", "/trade-api/ws/v2")

            logger.info(
                "websocket_connecting",
                url=self.ws_url,
                headers_present=list(extra_headers.keys())
            )

            self.websocket = await websockets.connect(
                self.ws_url,
                extra_headers=extra_headers,
                ping_interval=self.ping_interval,
                ping_timeout=60  # Increased from 20 to handle large market subscriptions
            )

            self.is_connected = True

            logger.info("websocket_connected")

            return True

        except Exception as e:
            logger.error("websocket_connection_failed", error=str(e), error_type=type(e).__name__)
            self.is_connected = False
            return False

    async def disconnect(self):
        """Disconnect from WebSocket."""
        if self.websocket:
            await self.websocket.close()
            self.is_connected = False
            logger.info("websocket_disconnected")

    async def subscribe_ticker_global(self):
        """
        Subscribe to global ticker channel for all markets.
        This gives us continuous price updates (tick data) for ALL markets.
        Must be called ONCE, not per-market.
        """
        if not self.is_connected or not self.websocket:
            logger.warning("cannot_subscribe_ticker_not_connected")
            return

        try:
            ticker_msg = {
                "id": 1,
                "cmd": "subscribe",
                "params": {
                    "channels": ["ticker"]
                    # NO market_ticker parameter - ticker is global
                }
            }

            await self.websocket.send(json.dumps(ticker_msg))
            logger.info("global_ticker_subscribed")

        except Exception as e:
            logger.error("ticker_subscription_failed", error=str(e))

    async def subscribe_market(self, ticker: str):
        """
        Subscribe to market-specific updates (trades and orderbook).

        Args:
            ticker: Market ticker to subscribe to
        """
        if not self.is_connected or not self.websocket:
            logger.warning("cannot_subscribe_not_connected", ticker=ticker)
            return

        try:
            # Subscribe to trades and orderbook for this market
            # Use unique ID based on number of subscribed markets
            market_msg = {
                "id": len(self.subscribed_markets) + 2,  # +2 to avoid ID collision with ticker (id=1)
                "cmd": "subscribe",
                "params": {
                    "channels": ["orderbook_delta", "trades"],
                    "market_ticker": ticker
                }
            }

            await self.websocket.send(json.dumps(market_msg))

            self.subscribed_markets.add(ticker)

            logger.info("market_subscribed", ticker=ticker)

        except Exception as e:
            logger.error("market_subscription_failed", ticker=ticker, error=str(e))

    async def subscribe_markets(self, tickers: list[str]):
        """
        Subscribe to multiple markets.
        First subscribes to global ticker channel, then subscribes to each market individually.

        Args:
            tickers: List of market tickers
        """
        # Subscribe to global ticker channel ONCE for all markets
        await self.subscribe_ticker_global()
        await asyncio.sleep(0.5)

        # Then subscribe to trades and orderbook for each market
        # No delay needed - Kalshi can handle rapid subscriptions
        for ticker in tickers:
            await self.subscribe_market(ticker)

    async def handle_message(self, message: Dict[str, Any]):
        """
        Handle incoming WebSocket message.

        Args:
            message: Parsed WebSocket message
        """
        msg_type = message.get("type")

        try:
            if msg_type == "orderbook_delta":
                await self._handle_orderbook_delta(message)

            elif msg_type == "ticker":
                await self._handle_ticker(message)

            elif msg_type == "trade":
                await self._handle_trade(message)

            elif msg_type == "subscribed":
                logger.debug("subscription_confirmed", message=message)

            elif msg_type == "error":
                logger.error("websocket_error_message", message=message)

            else:
                logger.debug("unknown_message_type", type=msg_type)

        except Exception as e:
            logger.error("message_handling_failed", error=str(e), message=message)

    async def _handle_ticker(self, message: Dict[str, Any]):
        """Handle ticker update message."""
        try:
            ticker = message.get("ticker")
            if not ticker:
                return

            now = datetime.utcnow()
            timestamp = int(now.timestamp())
            timestamp_ms = int(now.timestamp() * 1000)

            # Extract price data
            yes_bid = message.get("yes_bid")
            yes_ask = message.get("yes_ask")
            no_bid = message.get("no_bid")
            no_ask = message.get("no_ask")
            last_price = message.get("last_price")

            # Calculate mid price and spread
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
                last_price=last_price,
                yes_bid_size=message.get("yes_bid_size"),
                yes_ask_size=message.get("yes_ask_size"),
                no_bid_size=message.get("no_bid_size"),
                no_ask_size=message.get("no_ask_size"),
                volume=message.get("volume"),
                volume_24h=message.get("volume_24h"),
                open_interest=message.get("open_interest"),
                mid_price=mid_price,
                spread=spread
            )

            # Queue for batch insert
            await self.db.queue_snapshot(snapshot)

            logger.debug(
                "ticker_processed",
                ticker=ticker,
                yes_bid=yes_bid,
                yes_ask=yes_ask
            )

        except Exception as e:
            logger.error("ticker_handling_failed", error=str(e), message=message)

    async def _handle_trade(self, message: Dict[str, Any]):
        """Handle trade execution message."""
        try:
            ticker = message.get("ticker")
            if not ticker:
                return

            now = datetime.utcnow()
            timestamp = int(now.timestamp())
            timestamp_ms = int(now.timestamp() * 1000)

            trade = Trade(
                market_ticker=ticker,
                trade_id=message.get("trade_id"),
                timestamp=timestamp,
                timestamp_ms=timestamp_ms,
                price=message.get("price"),
                size=message.get("count", message.get("size", 1)),
                side=message.get("side"),
                taker_side=message.get("taker_side")
            )

            # Insert trades immediately (they're less frequent than ticks)
            await self.db.insert_trades([trade])

            logger.debug(
                "trade_processed",
                ticker=ticker,
                price=trade.price,
                size=trade.size
            )

        except Exception as e:
            logger.error("trade_handling_failed", error=str(e), message=message)

    async def _handle_orderbook_delta(self, message: Dict[str, Any]):
        """Handle orderbook delta update."""
        try:
            ticker = message.get("ticker")
            if not ticker:
                return

            # This is a delta update - in production you'd maintain full orderbook state
            # For now, we'll log the deltas
            logger.debug(
                "orderbook_delta_received",
                ticker=ticker,
                message=message
            )

            # You can implement full orderbook tracking here if needed

        except Exception as e:
            logger.error("orderbook_delta_handling_failed", error=str(e))

    async def listen(self):
        """Listen for WebSocket messages."""
        if not self.websocket:
            logger.error("listen_called_without_connection")
            return

        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self.handle_message(data)

                except json.JSONDecodeError as e:
                    logger.error("message_json_decode_failed", error=str(e))

        except websockets.exceptions.ConnectionClosed:
            logger.warning("websocket_connection_closed")
            self.is_connected = False

        except Exception as e:
            logger.error("websocket_listen_error", error=str(e))
            self.is_connected = False

    async def run_with_reconnect(self, market_tickers: list[str]):
        """
        Run WebSocket with automatic reconnection.

        Args:
            market_tickers: Markets to subscribe to
        """
        attempt = 0

        while attempt < self.max_reconnect_attempts:
            try:
                # Connect
                if not await self.connect():
                    attempt += 1
                    await asyncio.sleep(self.reconnect_delay * (2 ** attempt))
                    continue

                # Reset attempt counter on successful connection
                attempt = 0

                # Subscribe to markets
                await self.subscribe_markets(market_tickers)

                # Listen for messages
                await self.listen()

            except Exception as e:
                logger.error("websocket_run_error", error=str(e))

            # Connection lost, try to reconnect
            self.is_connected = False
            attempt += 1

            if attempt < self.max_reconnect_attempts:
                delay = self.reconnect_delay * (2 ** attempt)
                logger.info(
                    "websocket_reconnecting",
                    attempt=attempt,
                    delay_seconds=delay
                )
                await asyncio.sleep(delay)

        logger.error("websocket_max_reconnect_attempts_reached")

    async def close(self):
        """Close WebSocket connection."""
        await self.disconnect()
        logger.info("live_stream_closed")
