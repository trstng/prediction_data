# Pre-Deployment Checklist

## ✅ What's Complete

### Database (Supabase)
- ✅ 7 new tables created and configured:
  - `market_metadata` - Market information
  - `market_snapshots` - Tick data (0 rows - ready for data)
  - `orderbook_depth` - Order book snapshots (0 rows - ready for data)
  - `trades` - Trade executions (0 rows - ready for data)
  - `historical_prices` - OHLC data (0 rows - ready for data)
  - `data_collection_logs` - System logs (0 rows - ready for data)
  - `collection_health` - Health metrics (0 rows - ready for data)
- ✅ All tables have RLS policies enabled
- ✅ Proper indexes configured for performance
- ✅ Foreign key relationships established

### Application Code
- ✅ Complete Python application (2,500+ lines)
- ✅ Data collectors (WebSocket, REST, Historical)
- ✅ Market discovery system
- ✅ Health monitoring
- ✅ Rate limiting
- ✅ Error handling and retry logic
- ✅ Structured logging

### Deployment Configuration
- ✅ Dockerfile created
- ✅ Railway.json configured
- ✅ Environment variables documented
- ✅ Health check endpoints
- ✅ Startup scripts

### Documentation
- ✅ README.md - Complete user guide
- ✅ DEPLOYMENT.md - Railway deployment steps
- ✅ QUICK_START.md - 5-minute setup
- ✅ PROJECT_SUMMARY.md - Architecture details
- ✅ This checklist!

## 📋 Before You Start

### Required Items

- [ ] **Kalshi API Credentials**
  - Email/password for your Kalshi account
  - Test login at https://kalshi.com

- [ ] **PolyRouter API Key**
  - Sign up at https://docs.polyrouter.io
  - Free tier: 10 requests/minute

- [ ] **Supabase Access**
  - ✅ Project created: `Kalshi` (rggnsdnqdlinhafmksmh)
  - [ ] Service role key copied
  - ✅ Tables created and ready

### Optional (for deployment)

- [ ] **GitHub Account**
  - For Railway deployment from Git

- [ ] **Railway Account**
  - Sign up at https://railway.app
  - Free tier available

## 🚀 Getting Started

### Step 1: Local Setup (Required)

```bash
# 1. Navigate to project
cd /Users/tgonz/Desktop/Kalshi/data

# 2. Create .env from example
cp .env.example .env

# 3. Edit .env with your credentials
nano .env  # or your preferred editor

# Required in .env:
# - KALSHI_API_KEY (your email)
# - KALSHI_API_SECRET (your password)
# - POLYROUTER_API_KEY (from PolyRouter)
# - SUPABASE_URL (already known: https://rggnsdnqdlinhafmksmh.supabase.co)
# - SUPABASE_KEY (service role key from Supabase dashboard)
```

### Step 2: Test Connections

```bash
# Run connection test
python test_connection.py

# Should see:
# ✅ PASS - Supabase
# ✅ PASS - Kalshi Auth
# ✅ PASS - Market Fetch
# 🎉 All tests passed!
```

### Step 3: Run Locally

```bash
# Start the collector
./run_local.sh

# Let it run for 5-10 minutes
# Monitor the logs for:
# - "markets_discovered"
# - "market_snapshots_inserted"
# - "data_collector_running"
```

### Step 4: Verify Data Collection

Open Supabase dashboard and run:

```sql
-- Check for discovered markets
SELECT COUNT(*) FROM market_metadata;

-- Check for incoming snapshots
SELECT COUNT(*) FROM market_snapshots;

-- View recent snapshots
SELECT * FROM market_snapshots
ORDER BY created_at DESC
LIMIT 10;
```

## 🎯 Next Steps

### If Local Test Succeeds

- [ ] Monitor locally for 1 hour
- [ ] Verify data quality
- [ ] Check database growth rate
- [ ] Proceed to Railway deployment (see DEPLOYMENT.md)

### If Local Test Fails

Common issues:

1. **"Authentication failed"**
   - Check KALSHI_API_KEY and KALSHI_API_SECRET in .env
   - Verify credentials work on Kalshi website

2. **"Supabase connection failed"**
   - Verify SUPABASE_KEY is the service role key (not anon)
   - Check project URL is correct

3. **"No markets found"**
   - Check if sports are in season
   - Try with TARGET_SPORTS=NFL only
   - Verify Kalshi API is accessible

## 📊 Success Metrics

Your bot is working correctly when:

- ✅ Health endpoint returns 200: `curl http://localhost:8000/health`
- ✅ Markets discovered: `SELECT COUNT(*) FROM market_metadata` > 0
- ✅ Snapshots flowing: `SELECT COUNT(*) FROM market_snapshots` increasing
- ✅ No critical errors: `SELECT * FROM data_collection_logs WHERE log_level='ERROR'`
- ✅ WebSocket connected: Check logs for "websocket_connected"

## 🚢 Deployment (Optional)

Once local testing succeeds:

1. [ ] Create GitHub repository
2. [ ] Push code to GitHub
3. [ ] Connect to Railway
4. [ ] Add environment variables in Railway
5. [ ] Deploy and monitor

See `DEPLOYMENT.md` for detailed steps.

## 📝 Important Notes

### Rate Limits
- **PolyRouter**: 10 req/min (free tier) - already configured
- **Kalshi REST**: 100 req/min (conservative) - already configured
- **WebSocket**: No rate limits - primary data source

### Expected Data Volume
- **Per market**: ~50MB/day with full orderbook
- **10 markets**: ~500MB/day
- **Monitor**: Supabase free tier is 500MB total

### Costs
- **Local**: $0 (free tiers)
- **Railway**: $5/month (Hobby plan) or free tier
- **Supabase**: Free tier sufficient initially, may need Pro ($25/month) later

## 🆘 Getting Help

1. **Read the docs**:
   - `README.md` - Complete guide
   - `QUICK_START.md` - Fast setup
   - `DEPLOYMENT.md` - Production deployment

2. **Check logs**:
   - Local: Terminal output
   - Railway: Dashboard → Logs

3. **Query health**:
   ```sql
   SELECT * FROM collection_health
   ORDER BY timestamp DESC LIMIT 10;
   ```

## 🎉 You're Ready!

Everything is built and configured. Just need to:

1. Add your API credentials to `.env`
2. Run `python test_connection.py`
3. Start collecting data with `./run_local.sh`

Good luck with your trading strategies! 🚀
