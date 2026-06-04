SELECT m.pool_id,
       COUNT(*) AS total_matches,
       SUM(CASE WHEN m.tb_beatmap_id IS NOT NULL THEN 1 ELSE 0 END) AS tb_matches
FROM matches m
{filter}
GROUP BY m.pool_id
ORDER BY m.pool_id
