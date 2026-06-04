SELECT g.match_id, g.beatmap_id, g.team_index, SUM(g.score) AS total_score
FROM game_scores g
{filter}
GROUP BY g.match_id, g.beatmap_id, g.team_index
ORDER BY g.match_id, g.beatmap_id
