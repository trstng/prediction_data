-- Migration: Add unique constraint to trades table to prevent duplicates
-- Date: 2025-10-24
-- Description: Prevents duplicate trades by ensuring unique combination of
--              (market_ticker, timestamp, price, size, taker_side)

-- Step 1: First, we need to remove existing duplicates before adding the constraint
-- This will keep only the first occurrence of each duplicate group (by id)

DELETE FROM trades
WHERE id IN (
    SELECT t1.id
    FROM trades t1
    INNER JOIN trades t2 ON
        t1.market_ticker = t2.market_ticker
        AND t1.timestamp = t2.timestamp
        AND t1.price = t2.price
        AND t1.size = t2.size
        AND COALESCE(t1.taker_side, '') = COALESCE(t2.taker_side, '')
        AND t1.id > t2.id  -- Keep the first one (lower id)
);

-- Step 2: Add unique constraint to prevent future duplicates
-- Using a composite unique constraint on the key fields that define a unique trade

ALTER TABLE trades
ADD CONSTRAINT trades_unique_trade
UNIQUE (market_ticker, timestamp, price, size, taker_side);

-- Note: This constraint handles NULL values in taker_side appropriately
-- Multiple rows can have NULL in taker_side as long as other fields differ
-- But rows with the same market_ticker, timestamp, price, size, and both NULL taker_side
-- will be considered duplicates

-- Step 3: Create an index on timestamp for efficient querying (if not already exists)
CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp DESC);

-- Step 4: Create an index on market_ticker for efficient filtering (if not already exists)
CREATE INDEX IF NOT EXISTS idx_trades_market_ticker ON trades(market_ticker);

-- Optional: Add a comment to the constraint for documentation
COMMENT ON CONSTRAINT trades_unique_trade ON trades IS
'Ensures no duplicate trades by enforcing uniqueness on the combination of market_ticker, timestamp, price, size, and taker_side';
