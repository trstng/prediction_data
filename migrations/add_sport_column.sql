-- Migration: Add sport column to market_snapshots and trades tables
-- Purpose: Enable efficient filtering and querying by sport without JOINs
-- Date: 2025-10-28

-- Add sport column to market_snapshots
ALTER TABLE market_snapshots
ADD COLUMN sport VARCHAR(50);

-- Add sport column to trades
ALTER TABLE trades
ADD COLUMN sport VARCHAR(50);

-- Backfill sport column in market_snapshots from market_metadata
UPDATE market_snapshots ms
SET sport = mm.series_ticker
FROM market_metadata mm
WHERE ms.market_ticker = mm.market_ticker
  AND mm.series_ticker IS NOT NULL;

-- Backfill sport column in trades from market_metadata
UPDATE trades t
SET sport = mm.series_ticker
FROM market_metadata mm
WHERE t.market_ticker = mm.market_ticker
  AND mm.series_ticker IS NOT NULL;

-- Create composite indexes for efficient sport + time range queries
CREATE INDEX idx_market_snapshots_sport_timestamp
ON market_snapshots(sport, timestamp DESC)
WHERE sport IS NOT NULL;

CREATE INDEX idx_trades_sport_timestamp
ON trades(sport, timestamp DESC)
WHERE sport IS NOT NULL;

-- Create simple sport indexes for filtering
CREATE INDEX idx_market_snapshots_sport
ON market_snapshots(sport)
WHERE sport IS NOT NULL;

CREATE INDEX idx_trades_sport
ON trades(sport)
WHERE sport IS NOT NULL;

-- Add comments for documentation
COMMENT ON COLUMN market_snapshots.sport IS 'Sport/category identifier (NFL, NBA, NHL, NCAAF, WEATHER) - denormalized from market_metadata.series_ticker for query performance';
COMMENT ON COLUMN trades.sport IS 'Sport/category identifier (NFL, NBA, NHL, NCAAF, WEATHER) - denormalized from market_metadata.series_ticker for query performance';
