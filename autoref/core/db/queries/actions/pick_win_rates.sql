WITH pick AS (
    SELECT a.match_id, a.beatmap_id, a.team_index AS picker_team
    FROM match_actions a
    WHERE a.step = 'PICK'
      AND a.turn = (
          SELECT MIN(a2.turn) FROM match_actions a2
          WHERE a2.match_id = a.match_id AND a2.beatmap_id = a.beatmap_id AND a2.step = 'PICK'
      )
      {filter}
),
map_winner AS (
    SELECT gs.match_id, gs.beatmap_id,
           (SELECT gs2.team_index FROM game_scores gs2
            WHERE gs2.match_id = gs.match_id AND gs2.beatmap_id = gs.beatmap_id
            GROUP BY gs2.team_index ORDER BY SUM(gs2.score) DESC LIMIT 1) AS winner_team
    FROM game_scores gs
    GROUP BY gs.match_id, gs.beatmap_id
)
SELECT p.beatmap_id,
       COUNT(*) AS picks,
       SUM(CASE WHEN p.picker_team = mw.winner_team THEN 1 ELSE 0 END) AS wins
FROM pick p
LEFT JOIN map_winner mw ON mw.match_id = p.match_id AND mw.beatmap_id = p.beatmap_id
GROUP BY p.beatmap_id
ORDER BY p.beatmap_id
