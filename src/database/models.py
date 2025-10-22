"""
Data models for Kalshi market data.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class MarketMetadata(BaseModel):
    """Market metadata model."""
    market_ticker: str
    event_ticker: str
    series_ticker: Optional[str] = None
    title: str
    subtitle: Optional[str] = None
    market_type: Optional[str] = None
    category: Optional[str] = None
    open_time: Optional[int] = None
    close_time: Optional[int] = None
    expected_expiration_time: Optional[int] = None
    settlement_value: Optional[str] = None
    result: Optional[str] = None
    status: str = "active"
    volume_24h: int = 0
    liquidity: Optional[float] = None
    can_close_early: bool = False
    expiration_value: Optional[str] = None
    open_interest: int = 0


class MarketSnapshot(BaseModel):
    """Market snapshot model - comprehensive state at a point in time."""
    market_ticker: str
    timestamp: int  # Unix seconds
    timestamp_ms: int  # Unix milliseconds

    # Price data
    yes_bid: Optional[int] = None
    yes_ask: Optional[int] = None
    no_bid: Optional[int] = None
    no_ask: Optional[int] = None
    last_price: Optional[int] = None

    # Size data
    yes_bid_size: Optional[int] = None
    yes_ask_size: Optional[int] = None
    no_bid_size: Optional[int] = None
    no_ask_size: Optional[int] = None

    # Market metrics
    volume: Optional[int] = None
    volume_24h: Optional[int] = None
    open_interest: Optional[int] = None

    # Derived metrics
    mid_price: Optional[float] = None
    spread: Optional[float] = None
    liquidity_score: Optional[float] = None


class OrderbookLevel(BaseModel):
    """Single level in orderbook."""
    price: int
    size: int


class OrderbookDepth(BaseModel):
    """Full orderbook depth snapshot."""
    market_ticker: str
    timestamp: int
    side: str  # 'yes' or 'no'
    orderbook: List[OrderbookLevel]


class Trade(BaseModel):
    """Individual trade execution."""
    market_ticker: str
    trade_id: Optional[str] = None
    timestamp: int
    timestamp_ms: Optional[int] = None
    price: int
    size: int
    side: Optional[str] = None  # 'yes' or 'no'
    taker_side: Optional[str] = None  # 'buy' or 'sell'


class HistoricalPrice(BaseModel):
    """Historical price data from PolyRouter."""
    market_ticker: str
    platform: str = "kalshi"
    timestamp: int
    interval: str  # 1m, 5m, 1h, 4h, 1d

    # OHLC
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: float

    # Volume and interest
    volume: Optional[int] = None
    open_interest: Optional[int] = None

    # Spread OHLC
    bid_open: Optional[float] = None
    bid_high: Optional[float] = None
    bid_low: Optional[float] = None
    bid_close: Optional[float] = None
    ask_open: Optional[float] = None
    ask_high: Optional[float] = None
    ask_low: Optional[float] = None
    ask_close: Optional[float] = None

    source: str = "polyrouter"


class DataCollectionLog(BaseModel):
    """Log entry for data collection events."""
    timestamp: int
    log_level: str  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    component: str
    message: str
    details: Optional[Dict[str, Any]] = None
    error_trace: Optional[str] = None


class CollectionHealth(BaseModel):
    """Health metrics for data collection."""
    timestamp: int
    component: str
    metrics: Dict[str, Any]
    is_healthy: bool = True


# Kalshi API response models

class KalshiMarket(BaseModel):
    """Kalshi market from API."""
    ticker: str
    event_ticker: str
    series_ticker: Optional[str] = None
    title: str
    subtitle: Optional[str] = None
    market_type: Optional[str] = None
    category: Optional[str] = None
    open_time: Optional[str] = None
    close_time: Optional[str] = None
    expected_expiration_time: Optional[str] = None
    status: str
    yes_bid: Optional[int] = None
    yes_ask: Optional[int] = None
    no_bid: Optional[int] = None
    no_ask: Optional[int] = None
    last_price: Optional[int] = None
    previous_yes_bid: Optional[int] = None
    previous_yes_ask: Optional[int] = None
    previous_price: Optional[int] = None
    volume: Optional[int] = None
    volume_24h: Optional[int] = None
    liquidity: Optional[int] = None
    open_interest: Optional[int] = None
    result: Optional[str] = None
    can_close_early: Optional[bool] = None
    expiration_value: Optional[str] = None


class KalshiOrderbookLevel(BaseModel):
    """Orderbook level from Kalshi."""
    price: int
    quantity: int


class KalshiOrderbook(BaseModel):
    """Orderbook from Kalshi API."""
    yes: List[KalshiOrderbookLevel] = []
    no: List[KalshiOrderbookLevel] = []


class KalshiTrade(BaseModel):
    """Trade from Kalshi API."""
    trade_id: Optional[str] = None
    ticker: str
    price: int
    count: int
    created_time: Optional[str] = None
    taker_side: Optional[str] = None
