SELECT * FROM game_scores
WHERE match_id = ?
ORDER BY turn, score DESC
