SELECT a.match_id, a.turn, a.team_index, a.step, a.beatmap_id
FROM match_actions a
{filter}
ORDER BY a.match_id, a.turn
