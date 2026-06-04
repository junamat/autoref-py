SELECT g.match_id, g.team_index, mt.team_name, m.pool_id,
       SUM(g.score) AS total_score
FROM game_scores g
LEFT JOIN match_teams mt
    ON mt.match_id = g.match_id AND mt.team_index = g.team_index
LEFT JOIN matches m
    ON m.match_id = g.match_id
{filter}
GROUP BY g.match_id, g.team_index, mt.team_name, m.pool_id
ORDER BY m.pool_id, g.match_id
