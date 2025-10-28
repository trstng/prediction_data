-- Migration: Add sport column to market_snapshots and trades tables (MINIMAL - NO INDEXES)
-- Purpose: Just add the columns, skip indexes to avoid timeout
-- Date: 2025-10-28

-- Add sport column to market_snapshots
ALTER TABLE market_snapshots
ADD COLUMN IF NOT EXISTS sport VARCHAR(50);

-- Add sport column to trades
ALTER TABLE trades
ADD COLUMN IF NOT EXISTS sport VARCHAR(50);
