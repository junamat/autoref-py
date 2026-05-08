SELECT g.*, mt.team_name, m.tb_beatmap_id
FROM game_scores g
LEFT JOIN match_teams mt
    ON mt.match_id = g.match_id AND mt.team_index = g.team_index
LEFT JOIN matches m
    ON m.match_id = g.match_id
{filter}
