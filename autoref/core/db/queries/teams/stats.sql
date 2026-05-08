SELECT
    t.team_name,
    COUNT(DISTINCT t.match_id) AS matches_played,
    COUNT(DISTINCT CASE WHEN m.winner_team = t.team_name THEN t.match_id END) AS wins
FROM match_teams t
JOIN matches m ON t.match_id = m.match_id
GROUP BY t.team_name
ORDER BY wins DESC
