ALTER TABLE matches ADD COLUMN osu_match_id INTEGER;

CREATE INDEX IF NOT EXISTS idx_matches_osu_match_id ON matches (osu_match_id);
