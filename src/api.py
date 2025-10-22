"""
FastAPI endpoints for Kalshi data collector.
Provides REST API for charting and real-time market data.
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from typing import Optional, List
import structlog

from config.settings import settings
from supabase import create_client

logger = structlog.get_logger()

app = FastAPI(title="Kalshi Data Collector", version="1.0.0")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supabase client
supabase = create_client(settings.supabase_url, settings.supabase_key)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "kalshi-data-collector",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for Railway."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.environment,
        "target_sports": settings.target_sports_list
    }


@app.get("/ping")
async def ping():
    """Simple ping endpoint."""
    return {"ping": "pong"}


# ============================================================================
# MARKET DATA ENDPOINTS FOR CHARTING
# ============================================================================

@app.get("/api/markets")
async def get_markets(
    sport: Optional[str] = Query(None, description="Filter by sport: NFL, NHL, NBA, CFB"),
    status: str = Query("active", description="Market status filter")
):
    """
    Get list of markets grouped by sport.
    Returns active markets with basic metadata.
    """
    try:
        query = supabase.table("market_metadata").select("*").eq("status", status)

        if sport:
            query = query.eq("series_ticker", f"KX{sport}GAME")

        response = query.order("title").execute()

        markets = response.data

        # Group by sport
        grouped = {}
        for market in markets:
            series = market.get("series_ticker", "")
            if "KXNFLGAME" in series:
                sport_key = "NFL"
            elif "KXNHLGAME" in series:
                sport_key = "NHL"
            elif "KXNBAGAME" in series:
                sport_key = "NBA"
            elif "KXNCAAFGAME" in series:
                sport_key = "CFB"
            else:
                sport_key = "OTHER"

            if sport_key not in grouped:
                grouped[sport_key] = []

            grouped[sport_key].append({
                "ticker": market["market_ticker"],
                "title": market["title"],
                "subtitle": market.get("subtitle"),
                "close_time": market.get("close_time"),
                "status": market["status"]
            })

        return {
            "markets": grouped,
            "total": len(markets)
        }

    except Exception as e:
        logger.error("get_markets_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/markets/{ticker}/latest")
async def get_latest_snapshot(ticker: str):
    """
    Get the most recent price snapshot for a market.
    Perfect for displaying current price.
    """
    try:
        response = supabase.table("market_snapshots")\
            .select("*")\
            .eq("market_ticker", ticker)\
            .order("timestamp", desc=True)\
            .limit(1)\
            .execute()

        if not response.data:
            raise HTTPException(status_code=404, detail="No data found for this market")

        snapshot = response.data[0]

        return {
            "ticker": ticker,
            "timestamp": snapshot["timestamp"],
            "timestamp_ms": snapshot["timestamp_ms"],
            "yes_bid": snapshot.get("yes_bid"),
            "yes_ask": snapshot.get("yes_ask"),
            "no_bid": snapshot.get("no_bid"),
            "no_ask": snapshot.get("no_ask"),
            "last_price": snapshot.get("last_price"),
            "mid_price": float(snapshot["mid_price"]) if snapshot.get("mid_price") else None,
            "spread": float(snapshot["spread"]) if snapshot.get("spread") else None,
            "volume": snapshot.get("volume"),
            "open_interest": snapshot.get("open_interest")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_latest_snapshot_failed", error=str(e), ticker=ticker)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/markets/{ticker}/history")
async def get_price_history(
    ticker: str,
    start_time: Optional[int] = Query(None, description="Start timestamp (Unix seconds)"),
    end_time: Optional[int] = Query(None, description="End timestamp (Unix seconds)"),
    limit: int = Query(1000, description="Max data points to return", le=5000)
):
    """
    Get historical price data for charting.
    Returns time series data formatted for ApexCharts.

    ApexCharts format:
    {
      series: [{
        name: 'Price',
        data: [[timestamp_ms, price], [timestamp_ms, price], ...]
      }]
    }
    """
    try:
        query = supabase.table("market_snapshots")\
            .select("timestamp_ms, mid_price, yes_bid, yes_ask, volume")\
            .eq("market_ticker", ticker)

        if start_time:
            query = query.gte("timestamp", start_time)
        if end_time:
            query = query.lte("timestamp", end_time)

        response = query.order("timestamp").limit(limit).execute()

        if not response.data:
            return {
                "ticker": ticker,
                "series": [],
                "count": 0
            }

        # Format for ApexCharts line chart
        price_data = []
        volume_data = []
        bid_data = []
        ask_data = []

        for snapshot in response.data:
            ts = snapshot["timestamp_ms"]

            # Mid price series
            if snapshot.get("mid_price"):
                price_data.append([ts, float(snapshot["mid_price"])])

            # Volume series
            if snapshot.get("volume"):
                volume_data.append([ts, snapshot["volume"]])

            # Bid/Ask series
            if snapshot.get("yes_bid"):
                bid_data.append([ts, snapshot["yes_bid"]])
            if snapshot.get("yes_ask"):
                ask_data.append([ts, snapshot["yes_ask"]])

        return {
            "ticker": ticker,
            "series": [
                {"name": "Mid Price", "data": price_data},
                {"name": "Yes Bid", "data": bid_data},
                {"name": "Yes Ask", "data": ask_data}
            ],
            "volume_series": [
                {"name": "Volume", "data": volume_data}
            ],
            "count": len(response.data),
            "start_time": response.data[0]["timestamp_ms"] if response.data else None,
            "end_time": response.data[-1]["timestamp_ms"] if response.data else None
        }

    except Exception as e:
        logger.error("get_price_history_failed", error=str(e), ticker=ticker)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/markets/{ticker}/trades")
async def get_recent_trades(
    ticker: str,
    limit: int = Query(100, description="Number of recent trades", le=500)
):
    """
    Get recent trades for a market.
    """
    try:
        response = supabase.table("trades")\
            .select("*")\
            .eq("market_ticker", ticker)\
            .order("timestamp", desc=True)\
            .limit(limit)\
            .execute()

        trades = []
        for trade in response.data:
            trades.append({
                "trade_id": trade.get("trade_id"),
                "timestamp": trade["timestamp"],
                "timestamp_ms": trade.get("timestamp_ms"),
                "price": trade["price"],
                "size": trade["size"],
                "side": trade.get("side"),
                "taker_side": trade.get("taker_side")
            })

        return {
            "ticker": ticker,
            "trades": trades,
            "count": len(trades)
        }

    except Exception as e:
        logger.error("get_recent_trades_failed", error=str(e), ticker=ticker)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/markets/{ticker}/candles")
async def get_candles(
    ticker: str,
    interval: str = Query("1m", description="Candle interval: 1m, 5m, 15m, 1h"),
    start_time: Optional[int] = Query(None, description="Start timestamp (Unix seconds)"),
    end_time: Optional[int] = Query(None, description="End timestamp (Unix seconds)"),
    limit: int = Query(500, description="Max candles to return", le=1000)
):
    """
    Aggregate tick data into OHLC candles.
    Returns candlestick data formatted for ApexCharts.

    ApexCharts candlestick format:
    {
      data: [
        {x: timestamp, y: [open, high, low, close]},
        {x: timestamp, y: [open, high, low, close]},
        ...
      ]
    }
    """
    try:
        # Map interval to seconds
        interval_seconds = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "1h": 3600
        }.get(interval, 60)

        # Fetch raw snapshots
        query = supabase.table("market_snapshots")\
            .select("timestamp, mid_price")\
            .eq("market_ticker", ticker)

        if start_time:
            query = query.gte("timestamp", start_time)
        if end_time:
            query = query.lte("timestamp", end_time)

        response = query.order("timestamp").limit(5000).execute()

        if not response.data:
            return {"ticker": ticker, "interval": interval, "candles": [], "count": 0}

        # Aggregate into candles
        candles = {}
        for snapshot in response.data:
            if not snapshot.get("mid_price"):
                continue

            ts = snapshot["timestamp"]
            price = float(snapshot["mid_price"])

            # Round timestamp to interval
            candle_time = (ts // interval_seconds) * interval_seconds

            if candle_time not in candles:
                candles[candle_time] = {
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "count": 1
                }
            else:
                candles[candle_time]["high"] = max(candles[candle_time]["high"], price)
                candles[candle_time]["low"] = min(candles[candle_time]["low"], price)
                candles[candle_time]["close"] = price
                candles[candle_time]["count"] += 1

        # Format for ApexCharts
        candle_data = []
        for ts in sorted(candles.keys())[-limit:]:
            c = candles[ts]
            candle_data.append({
                "x": ts * 1000,  # Convert to milliseconds
                "y": [c["open"], c["high"], c["low"], c["close"]]
            })

        return {
            "ticker": ticker,
            "interval": interval,
            "candles": candle_data,
            "count": len(candle_data)
        }

    except Exception as e:
        logger.error("get_candles_failed", error=str(e), ticker=ticker)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
