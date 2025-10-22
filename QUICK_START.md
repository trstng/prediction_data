# Quick Start Guide

## 5-Minute Setup

### Step 1: Get Your Credentials

You'll need:
- ✅ Kalshi account email and password
- ✅ PolyRouter API key (from https://docs.polyrouter.io)
- ✅ Supabase project URL and service key

### Step 2: Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your credentials
nano .env  # or use your favorite editor
```

Required in `.env`:
```env
KALSHI_API_KEY=your_email@example.com
KALSHI_API_SECRET=your_password
POLYROUTER_API_KEY=your_polyrouter_key
SUPABASE_URL=https://rggnsdnqdlinhafmksmh.supabase.co
SUPABASE_KEY=your_service_role_key
```

### Step 3: Test Connection

```bash
# Make script executable
chmod +x run_local.sh

# Run connection test
python test_connection.py
```

You should see:
```
🎉 All tests passed! You're ready to start collecting data.
```

### Step 4: Run Locally

```bash
# Start the collector
./run_local.sh
```

Expected output:
```
🚀 Starting Kalshi Data Collector...
✅ Setup complete!
🎯 Starting data collector...

{"event": "kalshi_data_collector_starting", "version": "1.0.0"}
{"event": "orchestrator_initialized", "target_sports": ["NFL", "NHL", "NBA", "CFB"]}
{"event": "kalshi_login_successful", "expires_in_minutes": 25}
{"event": "markets_discovered", "series": "NFL", "count": 45}
{"event": "data_collector_running", "active_tasks": 5}
```

### Step 5: Verify Data Collection

Open another terminal and check Supabase:

```sql
-- Check discovered markets
SELECT market_ticker, title, status
FROM market_metadata
ORDER BY created_at DESC
LIMIT 10;

-- Check incoming snapshots
SELECT market_ticker, COUNT(*) as snapshot_count
FROM market_snapshots
WHERE created_at > NOW() - INTERVAL '5 minutes'
GROUP BY market_ticker;

-- Check health
SELECT *
FROM collection_health
ORDER BY timestamp DESC
LIMIT 5;
```

## Common Issues

### "Authentication failed"
- ✅ Double-check your Kalshi email/password in .env
- ✅ Ensure no extra spaces in credentials
- ✅ Try logging into Kalshi website to verify credentials

### "Supabase connection failed"
- ✅ Verify SUPABASE_URL is correct
- ✅ Use the service role key (not anon key)
- ✅ Check Supabase project is active

### "No markets found"
- ✅ Check if TARGET_SPORTS has active markets
- ✅ Try with just "NFL" first
- ✅ Verify Kalshi API is accessible

## What Happens Next?

Once running, the bot will:

1. **Discover Markets** (every 5 min)
   - Scans for active NFL, NHL, NBA, CFB markets
   - Saves to `market_metadata` table

2. **Collect Historical Data** (one-time)
   - Fetches last 7 days from PolyRouter
   - Saves to `historical_prices` table

3. **Stream Live Data** (continuous)
   - WebSocket: Real-time ticks every 1-5 seconds
   - REST: Backup polling every 3 seconds
   - Saves to `market_snapshots` and `trades` tables

4. **Monitor Health** (every 60 sec)
   - Tracks component performance
   - Saves to `collection_health` table

## Stopping the Bot

Press `Ctrl+C` to stop gracefully. The bot will:
- Close all connections
- Flush remaining data to database
- Save final health metrics

## Next Steps

1. **Monitor for 1 hour** - Verify data is flowing
2. **Check database size** - Plan storage needs
3. **Deploy to Railway** - See DEPLOYMENT.md
4. **Build backtest framework** - Start analyzing data!

## Quick Commands

```bash
# Test connections
python test_connection.py

# Run locally
./run_local.sh

# Check health (while running)
curl http://localhost:8000/health

# View logs (JSON format)
# Logs will appear in terminal where you ran ./run_local.sh
```

## Getting Help

- Check README.md for detailed documentation
- See DEPLOYMENT.md for Railway deployment
- Review PROJECT_SUMMARY.md for architecture details
- Check logs in terminal or Railway dashboard
