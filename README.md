# Kalshi Data Collection Bot

Standalone data collection system for streaming live Kalshi market data to Supabase for backtesting trading strategies.

## Features

- **Real-time WebSocket Streaming**: 1-5 second intervals for NFL, NHL, NBA, and College Football markets
- **Historical Data Backfill**: Fetch available historical data from PolyRouter API
- **REST API Polling**: Fallback/supplement to WebSocket for comprehensive coverage
- **Automatic Market Discovery**: Continuously finds and tracks new sports markets
- **Health Monitoring**: Built-in health checks and performance metrics
- **Rate Limiting**: Respects API limits with adaptive rate limiting
- **Database Optimization**: Batched inserts optimized for backtesting queries
- **Railway Deployment**: Ready for production deployment with auto-restart

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Data Collector Bot                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Market     │  │  Historical  │  │  WebSocket   │      │
│  │  Discovery   │  │   Backfill   │  │   Streamer   │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                 │                 │               │
│         └─────────────────┴─────────────────┘               │
│                         │                                   │
│                    ┌────▼────┐                              │
│                    │  REST   │                              │
│                    │ Poller  │                              │
│                    └────┬────┘                              │
│                         │                                   │
│                    ┌────▼────────┐                          │
│                    │  Database   │                          │
│                    │   Writer    │                          │
│                    └────┬────────┘                          │
│                         │                                   │
└─────────────────────────┼───────────────────────────────────┘
                          │
                          ▼
                   ┌──────────────┐
                   │   Supabase   │
                   └──────────────┘
```

## Database Schema

### Tables

- **market_metadata**: Static market information
- **market_snapshots**: Tick-by-tick price snapshots (1-5 sec intervals)
- **orderbook_depth**: Full orderbook snapshots
- **trades**: Individual trade executions
- **historical_prices**: OHLC data from PolyRouter
- **data_collection_logs**: System logs
- **collection_health**: Health metrics

## Setup

### 1. Environment Variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Required variables:
- `KALSHI_API_KEY`: Your Kalshi email
- `KALSHI_API_SECRET`: Your Kalshi password
- `POLYROUTER_API_KEY`: PolyRouter API key (10 req/min limit)
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_KEY`: Supabase service role key

### 2. Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Run Locally

```bash
# Run the data collector
python -m src.main
```

## Deployment to Railway

### 1. Create GitHub Repository

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-repo-url>
git push -u origin main
```

### 2. Deploy to Railway

1. Go to [Railway.app](https://railway.app)
2. Create new project from GitHub repo
3. Add environment variables in Railway dashboard:
   - Copy all variables from `.env`
   - Railway will auto-detect the Dockerfile

4. Deploy!

Railway will:
- Build the Docker image
- Run health checks on `/health`
- Auto-restart on failures
- Provide logs and metrics

## Configuration

### Data Collection Settings

```env
# Sports to track
TARGET_SPORTS=NFL,NHL,NBA,CFB

# How often to capture market snapshots (seconds)
COLLECTION_INTERVAL_SECONDS=3

# Enable/disable components
ENABLE_HISTORICAL_BACKFILL=true
ENABLE_LIVE_STREAMING=true
ENABLE_REST_POLLING=true
```

### Rate Limits

```env
POLYROUTER_REQUESTS_PER_MINUTE=10      # Free tier limit
KALSHI_REST_REQUESTS_PER_MINUTE=100    # Conservative limit
BATCH_INSERT_SIZE=500                  # Database batch size
```

## Monitoring

### Health Checks

Access health status:
```bash
curl http://localhost:8000/health
```

### Logs

The system uses structured JSON logging. View logs in Railway dashboard or locally:

```bash
python -m src.main | jq .
```

### Database Metrics

Query the `collection_health` table to monitor:
- WebSocket connection status
- Market discovery performance
- Database insert success rates
- API error rates

## Backtesting Queries

The data is optimized for common backtesting patterns:

### Get tick data for a market

```sql
SELECT
    timestamp,
    yes_bid,
    yes_ask,
    no_bid,
    no_ask,
    mid_price,
    spread,
    volume
FROM market_snapshots
WHERE market_ticker = 'MARKET_TICKER_HERE'
    AND timestamp BETWEEN start_ts AND end_ts
ORDER BY timestamp ASC;
```

### Get OHLC historical data

```sql
SELECT
    timestamp,
    interval,
    open,
    high,
    low,
    close,
    volume
FROM historical_prices
WHERE market_ticker = 'MARKET_TICKER_HERE'
    AND interval = '1h'
ORDER BY timestamp ASC;
```

### Get orderbook snapshots

```sql
SELECT
    timestamp,
    side,
    orderbook
FROM orderbook_depth
WHERE market_ticker = 'MARKET_TICKER_HERE'
    AND timestamp BETWEEN start_ts AND end_ts
ORDER BY timestamp ASC;
```

## Project Structure

```
kalshi-data-collector/
├── src/
│   ├── collectors/
│   │   ├── historical.py      # PolyRouter historical data
│   │   ├── live_stream.py     # Kalshi WebSocket
│   │   ├── rest_poller.py     # REST API fallback
│   │   └── kalshi_auth.py     # Authentication
│   ├── database/
│   │   ├── models.py          # Data models
│   │   └── writer.py          # Supabase operations
│   ├── discovery/
│   │   └── market_finder.py   # Market discovery
│   ├── monitoring/
│   │   └── health.py          # Health monitoring
│   ├── utils/
│   │   ├── logger.py          # Logging setup
│   │   └── rate_limiter.py    # Rate limiting
│   ├── main.py                # Main orchestrator
│   └── api.py                 # Health check API
├── config/
│   └── settings.py            # Configuration
├── Dockerfile
├── railway.json
├── requirements.txt
└── .env.example
```

## Troubleshooting

### WebSocket disconnects frequently
- Check Kalshi API status
- Verify authentication token refresh is working
- Review `data_collection_logs` table for errors

### Missing data points
- Check rate limiting metrics
- Verify markets are being discovered properly
- Review health check results

### Database insert failures
- Check Supabase connection
- Verify service role key has proper permissions
- Review batch size settings

## Contributing

This is a standalone project for personal use. Modify as needed for your trading strategies.

## License

MIT License - use at your own risk. No warranty provided.

## Disclaimer

This software is for educational and research purposes only. Trading involves risk. Always do your own research and never risk more than you can afford to lose.
