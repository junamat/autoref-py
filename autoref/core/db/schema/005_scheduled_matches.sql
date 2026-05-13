ALTER TABLE live_matches ADD COLUMN scheduled_at INTEGER;
ALTER TABLE live_matches ADD COLUMN assigned_ref_id INTEGER REFERENCES users(id)
