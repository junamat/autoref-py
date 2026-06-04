SELECT g.match_id, g.turn, g.team_index, SUM(g.score) AS total_score
FROM game_scores g
{filter}
GROUP BY g.match_id, g.turn, g.team_index
ORDER BY g.match_id, g.turn
