CREATE TABLE IF NOT EXISTS match_templates (
    id           INTEGER PRIMARY KEY,
    name         TEXT UNIQUE NOT NULL,
    payload_json TEXT NOT NULL,
    created_by   INTEGER REFERENCES users(id),
    created_at   INTEGER
)
