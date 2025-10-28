-- Fix tipoff times: expected_expiration_time is 3 hours late
-- Actual game tipoff is 3 hours (10800 seconds) earlier

UPDATE market_metadata
SET expected_expiration_time = expected_expiration_time - 10800
WHERE series_ticker = 'NBA'
  AND expected_expiration_time IS NOT NULL;

-- Also fix close_time if it has the same issue
-- (close_time appears to be correct based on charts, so commenting out)
-- UPDATE market_metadata
-- SET close_time = close_time - 10800
-- WHERE series_ticker = 'NBA'
--   AND close_time IS NOT NULL;
