SELECT DISTINCT pool_id, round_name
FROM matches
WHERE pool_id IS NOT NULL OR round_name IS NOT NULL
