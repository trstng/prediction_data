"""
Kalshi API authentication and REST client.
"""
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import httpx
import structlog
import time
import hashlib
import base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

from config.settings import settings

logger = structlog.get_logger()


class KalshiAuth:
    """Handles Kalshi API authentication and token management."""

    def __init__(self):
        """Initialize Kalshi authentication."""
        self.base_url = settings.kalshi_base_url
        self.api_key = settings.kalshi_api_key
        self.api_secret = settings.kalshi_api_secret

        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None

        # Load private key for signature-based auth
        self.private_key = None
        self._load_private_key()

        self.client = httpx.AsyncClient(timeout=30.0)

        logger.info("kalshi_auth_initialized", base_url=self.base_url)

    def _load_private_key(self):
        """Load RSA private key from settings."""
        try:
            # Handle both actual newlines and escaped \n sequences
            # Railway may convert newlines to literal \n strings
            key_string = self.api_secret
            if '\\n' in key_string:
                # Replace escaped newlines with actual newlines
                key_string = key_string.replace('\\n', '\n')

            key_bytes = key_string.encode('utf-8')
            self.private_key = serialization.load_pem_private_key(
                key_bytes,
                password=None,
                backend=default_backend()
            )
            logger.info("private_key_loaded_successfully")
        except Exception as e:
            logger.error("private_key_load_failed", error=str(e), key_preview=self.api_secret[:50] if self.api_secret else "None")
            self.private_key = None

    def _create_signature(self, timestamp: str, method: str, path: str, body: str = "") -> str:
        """
        Create signature for API request.

        Args:
            timestamp: Unix timestamp in milliseconds as string
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path
            body: Request body (empty for GET)

        Returns:
            Base64-encoded signature
        """
        if not self.private_key:
            return ""

        try:
            # Create message to sign: timestamp + method + path + body
            message = f"{timestamp}{method}{path}{body}"

            logger.debug(
                "creating_signature",
                timestamp=timestamp,
                method=method,
                path=path,
                message_preview=message[:100] if len(message) > 100 else message
            )

            # Sign the message
            signature = self.private_key.sign(
                message.encode('utf-8'),
                padding.PKCS1v15(),
                hashes.SHA256()
            )

            # Base64 encode
            return base64.b64encode(signature).decode('utf-8')

        except Exception as e:
            logger.error("signature_creation_failed", error=str(e))
            return ""

    async def login(self) -> bool:
        """
        Authenticate with Kalshi API.
        New API uses signature-based auth on each request, no login endpoint needed.

        Returns:
            True if authentication is set up correctly
        """
        if not self.private_key:
            logger.error("kalshi_auth_failed_no_private_key")
            return False

        # No actual login needed - we'll sign each request
        # Just validate we can make a test request
        try:
            # Test with a simple markets request
            timestamp = str(int(time.time() * 1000))
            path = "/trade-api/v2/markets"

            signature = self._create_signature(timestamp, "GET", path, "")

            headers = {
                "KALSHI-ACCESS-KEY": self.api_key,
                "KALSHI-ACCESS-SIGNATURE": signature,
                "KALSHI-ACCESS-TIMESTAMP": timestamp
            }

            response = await self.client.get(
                f"{self.base_url}/markets?limit=1",
                headers=headers
            )
            response.raise_for_status()

            logger.info("kalshi_auth_successful")
            return True

        except Exception as e:
            logger.error("kalshi_auth_failed", error=str(e), error_type=type(e).__name__)
            # Log more details for debugging
            if hasattr(e, 'response'):
                logger.error("kalshi_auth_response_details", status_code=e.response.status_code, response_text=e.response.text[:200])
            return False

    async def ensure_authenticated(self) -> bool:
        """
        Ensure we have a valid authentication setup.

        Returns:
            True if authenticated, False otherwise
        """
        return self.private_key is not None

    def get_signed_headers(self, method: str, path: str, body: str = "") -> Dict[str, str]:
        """
        Get headers with signature for API request.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path (e.g., "/trade-api/v2/markets")
            body: Request body as string (empty for GET)

        Returns:
            Headers dictionary with signature
        """
        timestamp = str(int(time.time() * 1000))
        signature = self._create_signature(timestamp, method, path, body)

        return {
            "KALSHI-ACCESS-KEY": self.api_key,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp
        }

    def get_headers(self) -> Dict[str, str]:
        """Get basic headers (deprecated - use get_signed_headers)."""
        return {}

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
        logger.info("kalshi_auth_closed")


class KalshiRestClient:
    """REST API client for Kalshi."""

    def __init__(self, auth: KalshiAuth):
        """
        Initialize REST client.

        Args:
            auth: KalshiAuth instance
        """
        self.auth = auth
        self.base_url = settings.kalshi_base_url
        self.client = httpx.AsyncClient(timeout=30.0)

        logger.info("kalshi_rest_client_initialized")

    async def get_markets(
        self,
        series_ticker: Optional[str] = None,
        event_ticker: Optional[str] = None,
        status: str = "open",
        limit: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Get markets from Kalshi API.

        Args:
            series_ticker: Filter by series (e.g., "KXNFLGAME", "KXNHLGAME")
            event_ticker: Filter by event ticker
            status: Market status filter
            limit: Max markets to return

        Returns:
            List of market data
        """
        await self.auth.ensure_authenticated()

        params = {"limit": limit, "status": status}
        if series_ticker:
            params["series_ticker"] = series_ticker
        if event_ticker:
            params["event_ticker"] = event_ticker

        # Build query string for signature (sorted for consistency)
        query_params = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        path = f"/trade-api/v2/markets?{query_params}"

        try:
            headers = self.auth.get_signed_headers("GET", path)

            response = await self.client.get(
                f"{self.base_url}/markets",
                headers=headers,
                params=params
            )
            response.raise_for_status()

            data = response.json()
            markets = data.get("markets", [])

            logger.info(
                "markets_fetched",
                count=len(markets),
                series=series_ticker,
                event_ticker=event_ticker,
                status=status
            )

            return markets

        except Exception as e:
            logger.error(
                "get_markets_failed",
                error=str(e),
                series=series_ticker,
                event_ticker=event_ticker
            )
            return []

    async def get_market(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get single market details.

        Args:
            ticker: Market ticker

        Returns:
            Market data or None
        """
        await self.auth.ensure_authenticated()

        path = f"/trade-api/v2/markets/{ticker}"

        try:
            headers = self.auth.get_signed_headers("GET", path)

            response = await self.client.get(
                f"{self.base_url}/markets/{ticker}",
                headers=headers
            )
            response.raise_for_status()

            data = response.json()
            market = data.get("market")

            logger.debug("market_fetched", ticker=ticker)

            return market

        except Exception as e:
            logger.error("get_market_failed", error=str(e), ticker=ticker)
            return None

    async def get_orderbook(self, ticker: str, depth: int = 10) -> Optional[Dict[str, Any]]:
        """
        Get market orderbook.

        Args:
            ticker: Market ticker
            depth: Orderbook depth

        Returns:
            Orderbook data or None
        """
        await self.auth.ensure_authenticated()

        path = f"/trade-api/v2/markets/{ticker}/orderbook?depth={depth}"

        try:
            headers = self.auth.get_signed_headers("GET", path)

            response = await self.client.get(
                f"{self.base_url}/markets/{ticker}/orderbook",
                headers=headers,
                params={"depth": depth}
            )
            response.raise_for_status()

            data = response.json()
            orderbook = data.get("orderbook")

            logger.debug("orderbook_fetched", ticker=ticker, depth=depth)

            return orderbook

        except Exception as e:
            logger.error("get_orderbook_failed", error=str(e), ticker=ticker)
            return None

    async def get_trades(
        self,
        ticker: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get recent trades.

        Args:
            ticker: Optional market ticker filter
            limit: Max trades to return

        Returns:
            List of trades
        """
        await self.auth.ensure_authenticated()

        params = {"limit": limit}
        if ticker:
            params["ticker"] = ticker

        # Build query string for signature
        query_params = "&".join([f"{k}={v}" for k, v in params.items()])
        path = f"/trade-api/v2/trades?{query_params}"

        try:
            headers = self.auth.get_signed_headers("GET", path)

            response = await self.client.get(
                f"{self.base_url}/trades",
                headers=headers,
                params=params
            )
            response.raise_for_status()

            data = response.json()
            trades = data.get("trades", [])

            logger.debug("trades_fetched", count=len(trades), ticker=ticker)

            return trades

        except Exception as e:
            logger.error("get_trades_failed", error=str(e), ticker=ticker)
            return []

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
        logger.info("kalshi_rest_client_closed")
