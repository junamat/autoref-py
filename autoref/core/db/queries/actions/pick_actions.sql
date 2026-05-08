SELECT a.match_id, a.turn, a.team_index AS picker_team,
       a.beatmap_id, m.round_name
FROM match_actions a
LEFT JOIN matches m ON m.match_id = a.match_id
WHERE a.step = 'PICK' {filter}
ORDER BY a.match_id, a.turn
