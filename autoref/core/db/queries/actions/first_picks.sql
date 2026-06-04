SELECT a.match_id, a.beatmap_id, a.team_index AS picker_team, m.pool_id
FROM match_actions a
LEFT JOIN matches m ON m.match_id = a.match_id
WHERE a.step = 'PICK'
  AND a.turn = (
      SELECT MIN(a2.turn) FROM match_actions a2
      WHERE a2.match_id = a.match_id AND a2.step = 'PICK'
  )
  {filter}
ORDER BY a.match_id
