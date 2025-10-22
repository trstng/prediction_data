# Kalshi Data Collector - Project Summary

## What Was Built

A production-ready, standalone data collection system that streams live Kalshi market data to Supabase for backtesting trading strategies.

## Key Components

### 1. Database Layer (Supabase)
- **7 comprehensive tables** optimized for backtesting
- Tables: market_metadata, market_snapshots, orderbook_depth, trades, historical_prices, data_collection_logs, collection_health
- Automatic RLS policies and proper indexing
- Optimized for time-series queries

### 2. Data Collectors

#### Historical Data Collector (`src/collectors/historical.py`)
- Fetches historical data from PolyRouter API
- Respects 10 req/min rate limit
- Supports multiple intervals (1m, 5m, 1h, 4h, 1d)
- Batch processing for efficiency

#### WebSocket Live Streamer (`src/collectors/live_stream.py`)
- Real-time market updates via Kalshi WebSocket
- Auto-reconnection with exponential backoff
- Subscribes to ticker, trade, and orderbook channels
- 1-5 second collection intervals

#### REST API Poller (`src/collectors/rest_poller.py`)
- Fallback/supplement to WebSocket
- Adaptive rate limiting (auto-adjusts on 429s)
- Polls market snapshots, orderbooks, and trades
- Configurable polling intervals

### 3. Market Discovery (`src/discovery/market_finder.py`)
- Automatically finds new markets in target sports
- Continuous discovery every 5 minutes
- Tracks market lifecycle (open → active → settled)
- Supports NFL, NHL, NBA, College Football

### 4. Health Monitoring (`src/monitoring/health.py`)
- Tracks component health metrics
- Monitors WebSocket connection status
- Tracks API success rates
- Database insert performance metrics
- Writes health data to database

### 5. Orchestration (`src/main.py`)
- Coordinates all components
- Manages component lifecycle
- Graceful shutdown handling
- Signal handling for production deployment
- Periodic market refresh

### 6. Utilities
- **Logger** (`src/utils/logger.py`): Structured JSON logging
- **Rate Limiter** (`src/utils/rate_limiter.py`): Token bucket with adaptive backoff
- **Settings** (`config/settings.py`): Pydantic-based configuration

## Data Flow

```
1. Market Discovery
   └─> Finds active sports markets
       └─> Saves to market_metadata

2. Historical Backfill (one-time)
   └─> Fetches available history from PolyRouter
       └─> Saves to historical_prices

3. Live Collection (continuous)
   ├─> WebSocket Stream
   │   ├─> Ticker updates → market_snapshots
   │   ├─> Trade events → trades
   │   └─> Orderbook deltas → orderbook_depth
   │
   └─> REST Polling (fallback)
       ├─> Market snapshots → market_snapshots
       ├─> Orderbook snapshots → orderbook_depth
       └─> Recent trades → trades

4. Health Monitoring (continuous)
   └─> Metrics → collection_health
   └─> Logs → data_collection_logs
```

## Features

### Reliability
- ✅ Auto-reconnection for WebSocket
- ✅ Graceful shutdown handling
- ✅ Error recovery and retry logic
- ✅ Health monitoring and alerting
- ✅ Structured logging for debugging

### Performance
- ✅ Batched database inserts
- ✅ Connection pooling
- ✅ Asynchronous operations
- ✅ Optimized queries with indexes
- ✅ Rate limiting to prevent throttling

### Deployment
- ✅ Dockerized application
- ✅ Railway-ready configuration
- ✅ Health check endpoints
- ✅ Environment-based configuration
- ✅ Auto-restart on failure

### Data Quality
- ✅ Microsecond timestamp precision
- ✅ Full orderbook capture
- ✅ Individual trade tracking
- ✅ Historical data backfill
- ✅ Data validation with Pydantic

## File Structure

```
kalshi-data-collector/
├── src/
│   ├── collectors/          # Data collection modules
│   │   ├── historical.py    # PolyRouter backfill
│   │   ├── live_stream.py   # WebSocket streaming
│   │   ├── rest_poller.py   # REST fallback
│   │   └── kalshi_auth.py   # Authentication
│   ├── database/            # Database layer
│   │   ├── models.py        # Pydantic models
│   │   └── writer.py        # Supabase operations
│   ├── discovery/           # Market discovery
│   │   └── market_finder.py
│   ├── monitoring/          # Health monitoring
│   │   └── health.py
│   ├── utils/               # Utilities
│   │   ├── logger.py
│   │   └── rate_limiter.py
│   ├── main.py              # Main orchestrator
│   └── api.py               # Health check API
├── config/
│   └── settings.py          # Configuration
├── Dockerfile               # Docker container
├── railway.json             # Railway config
├── requirements.txt         # Python dependencies
├── .env.example             # Example environment
├── README.md                # User documentation
├── DEPLOYMENT.md            # Deployment guide
└── test_connection.py       # Connection testing
```

## Configuration Options

### Sports
- NFL, NHL, NBA, College Football
- Easily extensible to other sports

### Collection Intervals
- WebSocket: Real-time (event-driven)
- REST Polling: 1-5 seconds (configurable)
- Market Discovery: 5 minutes
- Health Checks: 60 seconds

### Rate Limits
- PolyRouter: 10 requests/minute (free tier)
- Kalshi REST: 100 requests/minute (conservative)
- Adaptive rate limiting adjusts on 429s

### Database
- Batch inserts: 500 rows (configurable)
- Connection pooling enabled
- Auto-flush on shutdown

## Backtesting Use Cases

The collected data supports:

1. **Market Making Strategies**
   - Full orderbook depth
   - Bid-ask spreads
   - Liquidity metrics

2. **Mean Reversion**
   - Historical price data
   - OHLC intervals
   - Volume analysis

3. **Spread Farming**
   - Multi-market correlations
   - Cross-market spreads
   - Arbitrage opportunities

4. **Scalping**
   - Tick-by-tick data
   - Trade executions
   - Microsecond timestamps

5. **Momentum Trading**
   - Price movements
   - Volume spikes
   - Market sentiment

## Next Steps

### Immediate (Before Deployment)
1. ✅ Copy `.env.example` to `.env`
2. ✅ Fill in API credentials
3. ✅ Run `python test_connection.py`
4. ✅ Test locally with `./run_local.sh`

### Short Term (First Week)
1. Monitor data collection for 24-48 hours
2. Verify data quality and completeness
3. Adjust collection intervals if needed
4. Set up automated backups

### Medium Term (First Month)
1. Build backtesting framework
2. Develop trading strategies
3. Optimize database queries
4. Archive old data

### Long Term
1. Add more sports/markets
2. Implement real-time alerts
3. Build analytics dashboard
4. Scale infrastructure if needed

## Cost Estimates

### Development (Local)
- **Free**: All APIs have free tiers

### Production (Railway)
- **Railway**: $5/month (Hobby plan)
- **Supabase**: Free tier (may need Pro at $25/month for larger datasets)
- **PolyRouter**: Free tier (10 req/min)
- **Total**: $5-30/month depending on data volume

## Performance Metrics

Expected collection rates:
- **Market Snapshots**: 20-60 per market per minute
- **Trades**: Variable (depends on market activity)
- **Orderbook Snapshots**: 6-20 per market per minute
- **Historical Backfill**: 10 markets/minute (PolyRouter limit)

Database growth estimates:
- **Per market per day**: ~50MB (with full orderbook)
- **10 active markets**: ~500MB/day
- **Monthly**: ~15GB (10 markets, full collection)

## Support Resources

- **README.md**: Complete user documentation
- **DEPLOYMENT.md**: Step-by-step deployment guide
- **test_connection.py**: Verify setup before deployment
- **Inline documentation**: Comprehensive code comments

## Success Criteria

The bot is working correctly when:
1. ✅ Health check returns 200 OK
2. ✅ Markets are being discovered continuously
3. ✅ Snapshots are being inserted every 1-5 seconds
4. ✅ No errors in `data_collection_logs`
5. ✅ WebSocket stays connected
6. ✅ Database size is growing steadily

## Known Limitations

1. **PolyRouter Rate Limit**: 10 req/min on free tier
2. **Historical Data**: May not be available for all markets
3. **Supabase Storage**: Free tier has 500MB limit
4. **WebSocket**: Kalshi WebSocket URL may need verification

## Future Enhancements

Potential additions:
- Dashboard for monitoring collection
- Real-time alerts for anomalies
- Machine learning feature engineering
- Multi-region deployment
- Data export utilities
- Backtesting framework integration
