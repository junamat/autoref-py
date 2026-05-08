SELECT beatmap_id, step, COUNT(*) AS count
FROM match_actions
{filter}
GROUP BY beatmap_id, step
ORDER BY beatmap_id, step
