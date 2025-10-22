# Kalshi Data Collector - Charting API Guide

This guide explains the REST API endpoints available for charting Kalshi market data in your Vite + React frontend with ApexCharts.

## Base URL

```
http://localhost:8000  # Local development
https://your-railway-app.railway.app  # Production
```

All endpoints are prefixed with `/api`

---

## 🎯 Quick Start Example

```javascript
import { useState, useEffect } from 'react';
import Chart from 'react-apexcharts';

function PriceChart({ ticker }) {
  const [chartData, setChartData] = useState({ series: [] });

  useEffect(() => {
    fetch(`http://localhost:8000/api/markets/${ticker}/history?limit=1000`)
      .then(res => res.json())
      .then(data => setChartData({ series: data.series }));
  }, [ticker]);

  return (
    <Chart
      options={{
        chart: { type: 'line' },
        xaxis: { type: 'datetime' }
      }}
      series={chartData.series}
      type="line"
      height={350}
    />
  );
}
```

---

## 📊 Available Endpoints

### 1. **GET /api/markets** - List All Markets

**Purpose**: Get list of markets grouped by sport (NFL, NHL, NBA, CFB)

**Query Parameters**:
- `sport` (optional): Filter by sport - `NFL`, `NHL`, `NBA`, or `CFB`
- `status` (optional): Market status filter - `active` (default)

**Response Format**:
```json
{
  "markets": {
    "NFL": [
      {
        "ticker": "KXNFLGAME-25oct22bufne",
        "title": "Will Buffalo win vs New England?",
        "subtitle": "Buffalo vs New England - Oct 22, 2025",
        "close_time": "2025-10-22T20:00:00Z",
        "status": "active"
      }
    ],
    "NHL": [...],
    "NBA": [...],
    "CFB": [...]
  },
  "total": 326
}
```

**Frontend Usage**:
```javascript
// Get all markets
fetch('http://localhost:8000/api/markets')
  .then(res => res.json())
  .then(data => {
    const nflMarkets = data.markets.NFL;
    const nhlMarkets = data.markets.NHL;
    // etc...
  });

// Get only NFL markets
fetch('http://localhost:8000/api/markets?sport=NFL')
  .then(res => res.json())
  .then(data => {
    const nflMarkets = data.markets.NFL;
  });
```

---

### 2. **GET /api/markets/{ticker}/latest** - Current Price Snapshot

**Purpose**: Get the most recent price data for a market (for displaying current price)

**URL Parameters**:
- `ticker`: Market ticker (e.g., `KXNFLGAME-25oct22bufne`)

**Response Format**:
```json
{
  "ticker": "KXNFLGAME-25oct22bufne",
  "timestamp": 1729623456,
  "timestamp_ms": 1729623456789,
  "yes_bid": 52,
  "yes_ask": 54,
  "no_bid": 46,
  "no_ask": 48,
  "last_price": 53,
  "mid_price": 53.0,
  "spread": 2.0,
  "volume": 12543,
  "open_interest": 8932
}
```

**Frontend Usage**:
```javascript
function CurrentPrice({ ticker }) {
  const [price, setPrice] = useState(null);

  useEffect(() => {
    const fetchPrice = () => {
      fetch(`http://localhost:8000/api/markets/${ticker}/latest`)
        .then(res => res.json())
        .then(data => setPrice(data));
    };

    fetchPrice();
    const interval = setInterval(fetchPrice, 5000); // Update every 5 seconds
    return () => clearInterval(interval);
  }, [ticker]);

  if (!price) return <div>Loading...</div>;

  return (
    <div>
      <h3>{price.ticker}</h3>
      <p>Mid Price: {price.mid_price}¢</p>
      <p>Bid: {price.yes_bid}¢ | Ask: {price.yes_ask}¢</p>
      <p>Spread: {price.spread}¢</p>
      <p>Volume: {price.volume}</p>
    </div>
  );
}
```

---

### 3. **GET /api/markets/{ticker}/history** - Time Series Data for Line Charts

**Purpose**: Get historical price data formatted for ApexCharts line/area charts

**URL Parameters**:
- `ticker`: Market ticker

**Query Parameters**:
- `start_time` (optional): Start timestamp in Unix seconds
- `end_time` (optional): End timestamp in Unix seconds
- `limit` (optional): Max data points (default: 1000, max: 5000)

**Response Format** (ApexCharts-ready):
```json
{
  "ticker": "KXNFLGAME-25oct22bufne",
  "series": [
    {
      "name": "Mid Price",
      "data": [[1729623456789, 53.0], [1729623460123, 53.5], ...]
    },
    {
      "name": "Yes Bid",
      "data": [[1729623456789, 52], [1729623460123, 53], ...]
    },
    {
      "name": "Yes Ask",
      "data": [[1729623456789, 54], [1729623460123, 55], ...]
    }
  ],
  "volume_series": [
    {
      "name": "Volume",
      "data": [[1729623456789, 12543], [1729623460123, 12589], ...]
    }
  ],
  "count": 1000,
  "start_time": 1729623456789,
  "end_time": 1729626789012
}
```

**Frontend Usage with ApexCharts**:
```javascript
import Chart from 'react-apexcharts';

function PriceHistoryChart({ ticker }) {
  const [chartData, setChartData] = useState({ series: [] });

  useEffect(() => {
    // Get last 24 hours of data
    const now = Math.floor(Date.now() / 1000);
    const yesterday = now - (24 * 60 * 60);

    fetch(`http://localhost:8000/api/markets/${ticker}/history?start_time=${yesterday}&limit=2000`)
      .then(res => res.json())
      .then(data => setChartData({ series: data.series }));
  }, [ticker]);

  const options = {
    chart: {
      type: 'line',
      zoom: { enabled: true },
      toolbar: { show: true }
    },
    xaxis: {
      type: 'datetime',
      labels: {
        datetimeFormatter: {
          hour: 'HH:mm',
          minute: 'HH:mm'
        }
      }
    },
    yaxis: {
      title: { text: 'Price (¢)' },
      min: 0,
      max: 100
    },
    stroke: {
      curve: 'smooth',
      width: 2
    },
    colors: ['#00E396', '#008FFB', '#FEB019']
  };

  return (
    <Chart
      options={options}
      series={chartData.series}
      type="line"
      height={400}
    />
  );
}
```

---

### 4. **GET /api/markets/{ticker}/candles** - OHLC Candlestick Data

**Purpose**: Get aggregated OHLC (Open, High, Low, Close) candlestick data

**URL Parameters**:
- `ticker`: Market ticker

**Query Parameters**:
- `interval`: Candle interval - `1m`, `5m`, `15m`, `1h` (default: `1m`)
- `start_time` (optional): Start timestamp in Unix seconds
- `end_time` (optional): End timestamp in Unix seconds
- `limit` (optional): Max candles (default: 500, max: 1000)

**Response Format** (ApexCharts candlestick format):
```json
{
  "ticker": "KXNFLGAME-25oct22bufne",
  "interval": "5m",
  "candles": [
    {
      "x": 1729623456000,
      "y": [52.0, 55.0, 51.0, 54.0]  // [open, high, low, close]
    },
    {
      "x": 1729623756000,
      "y": [54.0, 56.0, 53.0, 55.0]
    }
  ],
  "count": 144
}
```

**Frontend Usage with ApexCharts**:
```javascript
function CandlestickChart({ ticker }) {
  const [candles, setCandles] = useState([]);
  const [interval, setInterval] = useState('5m');

  useEffect(() => {
    fetch(`http://localhost:8000/api/markets/${ticker}/candles?interval=${interval}&limit=500`)
      .then(res => res.json())
      .then(data => setCandles(data.candles));
  }, [ticker, interval]);

  const options = {
    chart: {
      type: 'candlestick',
      toolbar: { show: true }
    },
    xaxis: {
      type: 'datetime'
    },
    yaxis: {
      tooltip: { enabled: true },
      title: { text: 'Price (¢)' }
    }
  };

  return (
    <div>
      <select value={interval} onChange={(e) => setInterval(e.target.value)}>
        <option value="1m">1 Minute</option>
        <option value="5m">5 Minutes</option>
        <option value="15m">15 Minutes</option>
        <option value="1h">1 Hour</option>
      </select>

      <Chart
        options={options}
        series={[{ data: candles }]}
        type="candlestick"
        height={400}
      />
    </div>
  );
}
```

---

### 5. **GET /api/markets/{ticker}/trades** - Recent Trade History

**Purpose**: Get list of recent trade executions

**URL Parameters**:
- `ticker`: Market ticker

**Query Parameters**:
- `limit` (optional): Number of trades to return (default: 100, max: 500)

**Response Format**:
```json
{
  "ticker": "KXNFLGAME-25oct22bufne",
  "trades": [
    {
      "trade_id": "abc123",
      "timestamp": 1729623456,
      "timestamp_ms": 1729623456789,
      "price": 53,
      "size": 100,
      "side": "yes",
      "taker_side": "buy"
    }
  ],
  "count": 100
}
```

**Frontend Usage**:
```javascript
function TradeHistory({ ticker }) {
  const [trades, setTrades] = useState([]);

  useEffect(() => {
    const fetchTrades = () => {
      fetch(`http://localhost:8000/api/markets/${ticker}/trades?limit=50`)
        .then(res => res.json())
        .then(data => setTrades(data.trades));
    };

    fetchTrades();
    const interval = setInterval(fetchTrades, 10000); // Update every 10 seconds
    return () => clearInterval(interval);
  }, [ticker]);

  return (
    <div className="trade-history">
      <h3>Recent Trades</h3>
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Price</th>
            <th>Size</th>
            <th>Side</th>
          </tr>
        </thead>
        <tbody>
          {trades.map(trade => (
            <tr key={trade.trade_id}>
              <td>{new Date(trade.timestamp_ms).toLocaleTimeString()}</td>
              <td>{trade.price}¢</td>
              <td>{trade.size}</td>
              <td className={trade.taker_side === 'buy' ? 'text-green' : 'text-red'}>
                {trade.taker_side}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

---

## 🔄 Real-time Updates

The API returns **tick data** (every price change from the WebSocket), not just trades. For real-time charts, poll the `/latest` or `/history` endpoints:

```javascript
function RealTimeChart({ ticker }) {
  const [series, setSeries] = useState([{ name: 'Mid Price', data: [] }]);

  useEffect(() => {
    const fetchData = async () => {
      const res = await fetch(`http://localhost:8000/api/markets/${ticker}/history?limit=100`);
      const data = await res.json();
      setSeries(data.series);
    };

    fetchData(); // Initial fetch
    const interval = setInterval(fetchData, 3000); // Update every 3 seconds

    return () => clearInterval(interval);
  }, [ticker]);

  return <Chart series={series} type="line" />;
}
```

**Note**: For production, consider using Supabase Realtime subscriptions for true real-time updates instead of polling.

---

## 📦 Complete Example: Multi-Market Dashboard

```javascript
import { useState, useEffect } from 'react';
import Chart from 'react-apexcharts';

function MarketDashboard() {
  const [markets, setMarkets] = useState({ NFL: [], NHL: [], NBA: [], CFB: [] });
  const [selectedMarket, setSelectedMarket] = useState(null);
  const [chartData, setChartData] = useState({ series: [] });
  const [currentPrice, setCurrentPrice] = useState(null);

  // Load markets on mount
  useEffect(() => {
    fetch('http://localhost:8000/api/markets')
      .then(res => res.json())
      .then(data => setMarkets(data.markets));
  }, []);

  // Load chart data when market is selected
  useEffect(() => {
    if (!selectedMarket) return;

    const fetchData = async () => {
      // Get historical data
      const historyRes = await fetch(`http://localhost:8000/api/markets/${selectedMarket}/history?limit=500`);
      const historyData = await historyRes.json();
      setChartData({ series: historyData.series });

      // Get current price
      const priceRes = await fetch(`http://localhost:8000/api/markets/${selectedMarket}/latest`);
      const priceData = await priceRes.json();
      setCurrentPrice(priceData);
    };

    fetchData();
    const interval = setInterval(fetchData, 5000); // Update every 5 seconds

    return () => clearInterval(interval);
  }, [selectedMarket]);

  return (
    <div className="dashboard">
      <div className="sidebar">
        <h2>Markets</h2>
        {Object.entries(markets).map(([sport, sportMarkets]) => (
          <div key={sport}>
            <h3>{sport}</h3>
            {sportMarkets.map(market => (
              <button
                key={market.ticker}
                onClick={() => setSelectedMarket(market.ticker)}
                className={selectedMarket === market.ticker ? 'active' : ''}
              >
                {market.title}
              </button>
            ))}
          </div>
        ))}
      </div>

      <div className="main-content">
        {selectedMarket && currentPrice && (
          <>
            <div className="price-header">
              <h2>{currentPrice.ticker}</h2>
              <div className="price-info">
                <span>Mid: {currentPrice.mid_price}¢</span>
                <span>Bid: {currentPrice.yes_bid}¢</span>
                <span>Ask: {currentPrice.yes_ask}¢</span>
                <span>Spread: {currentPrice.spread}¢</span>
              </div>
            </div>

            <Chart
              options={{
                chart: { type: 'line', zoom: { enabled: true } },
                xaxis: { type: 'datetime' },
                yaxis: { min: 0, max: 100 }
              }}
              series={chartData.series}
              type="line"
              height={400}
            />
          </>
        )}
      </div>
    </div>
  );
}

export default MarketDashboard;
```

---

## 🎨 Data Format Summary

All endpoints return data in **ApexCharts-compatible format**:

- **Line/Area Charts**: `[[timestamp_ms, value], [timestamp_ms, value], ...]`
- **Candlestick Charts**: `[{x: timestamp_ms, y: [open, high, low, close]}, ...]`
- **Timestamps**: Always in milliseconds (multiply Unix seconds by 1000)
- **Prices**: In cents (0-100 range)

---

## 🚀 Best Practices

1. **Use polling intervals wisely**: 3-5 seconds for active charts, 10-30 seconds for background updates
2. **Limit data points**: Use `limit` parameter to avoid loading too much data (500-1000 points is usually enough)
3. **Filter by time**: Use `start_time` and `end_time` to get specific time ranges
4. **Cache aggressively**: Store market lists locally, only refresh periodically
5. **Handle errors**: Always add error handling for failed API calls

---

## 🔧 CORS Configuration

The API has CORS enabled for all origins (`allow_origins=["*"]`). In production, update this in `src/api.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend.com"],  # Your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 📝 Environment Variables

Make sure your frontend has the correct API URL:

```javascript
// .env.local
VITE_API_URL=http://localhost:8000  # Local
VITE_API_URL=https://your-railway-app.railway.app  # Production

// Usage in code
const API_URL = import.meta.env.VITE_API_URL;
fetch(`${API_URL}/api/markets`);
```
