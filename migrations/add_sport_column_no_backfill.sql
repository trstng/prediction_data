-- Migration: Add sport column to market_snapshots and trades tables (NO BACKFILL)
-- Purpose: Enable efficient filtering and querying by sport without JOINs
-- Date: 2025-10-28
-- Note: Skips backfill of historical data - only new data will have sport populated

-- Add sport column to market_snapshots
ALTER TABLE market_snapshots
ADD COLUMN IF NOT EXISTS sport VARCHAR(50);

-- Add sport column to trades
ALTER TABLE trades
ADD COLUMN IF NOT EXISTS sport VARCHAR(50);

-- Create composite indexes for efficient sport + time range queries
CREATE INDEX IF NOT EXISTS idx_market_snapshots_sport_timestamp
ON market_snapshots(sport, timestamp DESC)
WHERE sport IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_trades_sport_timestamp
ON trades(sport, timestamp DESC)
WHERE sport IS NOT NULL;

-- Create simple sport indexes for filtering
CREATE INDEX IF NOT EXISTS idx_market_snapshots_sport
ON market_snapshots(sport)
WHERE sport IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_trades_sport
ON trades(sport)
WHERE sport IS NOT NULL;

-- Add comments for documentation
COMMENT ON COLUMN market_snapshots.sport IS 'Sport/category identifier (NFL, NBA, NHL, NCAAF, WEATHER) - denormalized from market_metadata.series_ticker for query performance';
COMMENT ON COLUMN trades.sport IS 'Sport/category identifier (NFL, NBA, NHL, NCAAF, WEATHER) - denormalized from market_metadata.series_ticker for query performance';
