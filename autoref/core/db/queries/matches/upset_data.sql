SELECT m.round_name,
       m.match_id,
       m.winner_team,
       mt_low.team_name AS lower_seed_team,
       mt_low.seed AS lower_seed,
       mt_high.seed AS higher_seed
FROM matches m
JOIN match_teams mt_low ON mt_low.match_id = m.match_id
JOIN match_teams mt_high ON mt_high.match_id = m.match_id
    AND mt_high.team_index != mt_low.team_index
WHERE mt_low.seed IS NOT NULL
  AND mt_high.seed IS NOT NULL
  AND mt_low.seed > mt_high.seed
  {filter}
ORDER BY m.round_name, m.match_id
