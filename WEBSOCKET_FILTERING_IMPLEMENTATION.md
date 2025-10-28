# WebSocket Data Filtering & Sport Column Implementation

## Summary

Successfully implemented comprehensive filtering for WebSocket data collection to only capture NBA, NHL, NFL, NCAAF, and weather markets. Added a denormalized `sport` column to `market_snapshots` and `trades` tables for optimal query performance.

## Changes Made

### 1. Database Schema (Migration Required)

**File:** `migrations/add_sport_column.sql`

- Added `sport VARCHAR(50)` column to `market_snapshots` table
- Added `sport VARCHAR(50)` column to `trades` table
- Created composite indexes: `idx_market_snapshots_sport_timestamp` and `idx_trades_sport_timestamp`
- Created simple indexes: `idx_market_snapshots_sport` and `idx_trades_sport`
- Added backfill queries to populate sport from existing `market_metadata.series_ticker`

**Action Required:** Apply this migration to your Supabase database

```bash
# You can run this via Supabase SQL Editor or via your migration tool
psql <your_supabase_connection_string> < migrations/add_sport_column.sql
```

### 2. Database Models

**File:** `src/database/models.py`

- Added `sport: Optional[str]` field to `MarketSnapshot` class (line 46)
- Added `sport: Optional[str]` field to `Trade` class (line 98)
- Sport field accepts: "NFL", "NBA", "NHL", "NCAAF", "WEATHER"

### 3. WebSocket Collector

**File:** `src/collectors/live_stream.py`

**Key Changes:**
- Added `ticker_to_sport: Dict[str, str]` cache to `__init__()` (line 45)
- Updated `subscribe_markets()` to accept `market_metadata` parameter and build sport cache (lines 161-189)
- Added filtering in `_handle_ticker()` to only process subscribed markets (lines 231-233)
- Added sport field to MarketSnapshot in `_handle_ticker()` (line 259)
- Added filtering in `_handle_trade()` to only process subscribed markets (lines 299-301)
- Added sport field to Trade in `_handle_trade()` (line 329)
- Updated `run_with_reconnect()` to pass market_metadata (line 391)

**Filtering Mechanism:**
- Global ticker channel still receives ALL Kalshi markets (unavoidable with their WebSocket API)
- Handler methods now check `if ticker not in self.subscribed_markets` and return early
- This prevents unwanted data from being inserted into the database

### 4. REST Poller

**File:** `src/collectors/rest_poller.py`

**Key Changes:**
- Added `ticker_to_sport: Dict[str, str]` cache to `__init__()` (line 43)
- Added sport field to snapshots in `poll_market_snapshot()` (line 76, 99)
- Updated `update_active_markets()` to accept `market_metadata` and build sport cache (lines 309-331)

### 5. Market Discovery

**File:** `src/discovery/market_finder.py`

**Key Changes:**
- Updated `series_ticker_map` to include NCAAF and weather (lines 82-90):
  - Changed "CFB" to "NCAAF" (kept CFB as alias for backwards compatibility)
  - Added "WEATHER" with multiple series: KXHIGHLAX, KXHIGHNY, KXHIGHAUS, KXHIGHMIA, KXHIGHCHI, KXHIGHDEN
- Updated `discover_markets_for_series()` to handle weather's multiple series (lines 97-152)
- Added `get_active_market_metadata()` method to return full MarketMetadata objects (lines 269-290)

### 6. Configuration

**Files:** `config/settings.py` and `.env.example`

- Updated `target_sports` default from "NFL,NHL,NBA,CFB" to "NFL,NHL,NBA,NCAAF,WEATHER"
- Changed in both `config/settings.py` (line 40) and `.env.example` (line 15)

**Action Required:** Update your `.env` file:
```bash
TARGET_SPORTS=NFL,NHL,NBA,NCAAF,WEATHER
```

### 7. Main Orchestrator

**File:** `src/main.py`

**Key Changes:**
- Updated `start_live_streaming()` to fetch and pass market_metadata (lines 106-123)
- Updated `start_rest_polling()` to fetch and pass market_metadata (lines 143-151)
- Updated `refresh_markets_periodically()` to fetch and pass market_metadata (lines 186-197)

## Data Flow

### Before (Collecting Everything)
```
WebSocket → Global Ticker (ALL markets) → Database
                                          ↓
                                    Unwanted data cluttering DB
```

### After (Filtered Collection)
```
WebSocket → Global Ticker (ALL markets) → Filter Handler → Database
                                              ↓
                                   Only NFL, NBA, NHL, NCAAF, WEATHER
                                   Each row tagged with sport column
```

## Query Performance Benefits

### Before (With JOINs)
```sql
-- Slow: Requires JOIN with market_metadata
SELECT * FROM market_snapshots ms
JOIN market_metadata mm ON ms.market_ticker = mm.market_ticker
WHERE mm.series_ticker = 'NBA'
AND ms.timestamp > ...
```

### After (Direct Filtering)
```sql
-- Fast: Direct index scan on sport column
SELECT * FROM market_snapshots
WHERE sport = 'NBA'
AND timestamp > ...

-- Uses index: idx_market_snapshots_sport_timestamp
```

## Testing Checklist

After deployment, verify the following:

1. **Migration Applied Successfully**
   ```sql
   -- Check columns exist
   SELECT column_name, data_type
   FROM information_schema.columns
   WHERE table_name IN ('market_snapshots', 'trades')
   AND column_name = 'sport';

   -- Check indexes exist
   SELECT indexname FROM pg_indexes
   WHERE tablename IN ('market_snapshots', 'trades')
   AND indexname LIKE '%sport%';
   ```

2. **Sport Cache Populated**
   - Check logs for: `sport_cache_built` with total_markets and sports list
   - Should see sports: {'NFL', 'NBA', 'NHL', 'NCAAF', 'WEATHER'}

3. **Filtering Working**
   - Monitor logs for `ticker_processed` messages
   - Verify only configured sports are being inserted
   - Check: `SELECT DISTINCT sport FROM market_snapshots ORDER BY sport;`
   - Expected: NBA, NCAAF, NFL, NHL, WEATHER (no politics, economics, etc.)

4. **Sport Column Populated**
   ```sql
   -- Check sport distribution
   SELECT sport, COUNT(*) as count
   FROM market_snapshots
   WHERE timestamp > extract(epoch from now() - interval '1 hour')
   GROUP BY sport
   ORDER BY sport;
   ```

5. **Query Performance**
   ```sql
   -- Test indexed query performance
   EXPLAIN ANALYZE
   SELECT * FROM market_snapshots
   WHERE sport = 'NBA'
   AND timestamp > extract(epoch from now() - interval '24 hours')
   ORDER BY timestamp DESC
   LIMIT 100;

   -- Should use index: idx_market_snapshots_sport_timestamp
   ```

## Troubleshooting

### Issue: Sport column is NULL in new rows

**Cause:** Market metadata not being passed to collectors

**Fix:** Check that `get_active_market_metadata()` is returning data:
```python
# Add debug logging in main.py
logger.info("market_metadata_fetched", count=len(market_metadata), sports=set(m.series_ticker for m in market_metadata))
```

### Issue: Still collecting unwanted markets

**Cause:** Filtering logic not working

**Fix:** Verify `subscribed_markets` set is populated:
```python
# In live_stream.py, add logging after subscribe_markets()
logger.info("subscribed_markets_set", count=len(self.subscribed_markets), sample=list(self.subscribed_markets)[:5])
```

### Issue: No weather markets found

**Cause:** Weather series tickers might have changed

**Fix:** Query Kalshi API for current weather series:
```bash
curl -X GET "https://api.elections.kalshi.com/trade-api/v2/series?limit=100&cursor=" \
  -H "Authorization: Bearer YOUR_TOKEN" | jq '.series[] | select(.ticker | startswith("KXHIGH"))'
```

## Future Enhancements

1. **Partitioning by Sport**
   - Consider partitioning large tables by sport for even better performance
   - Useful when data grows to millions of rows

2. **Dynamic Sport Configuration**
   - Add admin API to enable/disable sports without code changes
   - Store configuration in database

3. **Per-Sport Data Retention**
   - Different retention policies per sport (e.g., keep weather 30 days, sports 90 days)

4. **Sport-Specific Analytics**
   - Pre-aggregate metrics by sport for dashboard performance
   - Materialized views per sport

## File Summary

**Files Modified:** 8
**Files Created:** 2 (migration + this doc)

### Modified Files
1. `src/database/models.py` - Added sport fields
2. `src/collectors/live_stream.py` - Added filtering and sport caching
3. `src/collectors/rest_poller.py` - Added sport caching
4. `src/discovery/market_finder.py` - Added NCAAF/weather support
5. `src/main.py` - Pass metadata to collectors
6. `config/settings.py` - Updated default sports
7. `.env.example` - Updated example config
8. `src/database/writer.py` - No changes needed (uses model_dump)

### Created Files
1. `migrations/add_sport_column.sql` - Database schema migration
2. `WEBSOCKET_FILTERING_IMPLEMENTATION.md` - This document

## Deployment Steps

1. **Apply Database Migration**
   ```bash
   # Via Supabase SQL Editor or psql
   psql $DATABASE_URL < migrations/add_sport_column.sql
   ```

2. **Update Environment Variables**
   ```bash
   # In your .env file or Railway/hosting dashboard
   TARGET_SPORTS=NFL,NHL,NBA,NCAAF,WEATHER
   ```

3. **Deploy Code Changes**
   ```bash
   git add .
   git commit -m "Add sport filtering and denormalized sport column"
   git push origin main
   ```

4. **Verify Deployment**
   - Check logs for `sport_cache_built` message
   - Verify sport column is being populated
   - Confirm only target sports are being collected

5. **Monitor Performance**
   - Watch database query performance
   - Monitor disk usage (should stabilize or decrease)
   - Check data collection logs for errors

## Questions?

If you encounter any issues:
1. Check the troubleshooting section above
2. Review logs for error messages
3. Verify migration was applied correctly
4. Ensure `.env` has correct TARGET_SPORTS value
