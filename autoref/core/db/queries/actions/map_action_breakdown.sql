WITH per_match_map AS (
    SELECT
        match_id, beatmap_id,
        SUM(CASE WHEN step = 'PICK'    THEN 1 ELSE 0 END) AS picks,
        SUM(CASE WHEN step = 'BAN'     THEN 1 ELSE 0 END) AS bans,
        SUM(CASE WHEN step = 'PROTECT' THEN 1 ELSE 0 END) AS protects
    FROM match_actions
    {filter}
    GROUP BY match_id, beatmap_id
)
SELECT
    beatmap_id,
    SUM(bans)  AS bans,
    SUM(picks) AS picks,
    SUM(CASE WHEN protects > 0 THEN picks    ELSE 0 END) AS picks_while_protected,
    SUM(CASE WHEN picks    = 0 THEN protects ELSE 0 END) AS protect_only
FROM per_match_map
GROUP BY beatmap_id
ORDER BY beatmap_id
