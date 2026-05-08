CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS matches (
    match_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ruleset_vs        INTEGER NOT NULL,
    gamemode          TEXT NOT NULL,
    win_condition     TEXT NOT NULL,
    best_of           INTEGER NOT NULL DEFAULT 1,
    bans_per_team     TEXT NOT NULL DEFAULT '0',
    protects_per_team TEXT NOT NULL DEFAULT '0',
    winner_team       TEXT,
    pool_id           TEXT,
    round_name        TEXT,
    tb_beatmap_id     INTEGER
);

CREATE TABLE IF NOT EXISTS match_teams (
    match_id    INTEGER NOT NULL REFERENCES matches(match_id),
    team_index  INTEGER NOT NULL,
    team_name   TEXT NOT NULL,
    PRIMARY KEY (match_id, team_index)
);

CREATE TABLE IF NOT EXISTS match_actions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id    INTEGER NOT NULL REFERENCES matches(match_id),
    turn        INTEGER NOT NULL,
    team_index  INTEGER NOT NULL,
    step        TEXT NOT NULL,
    beatmap_id  INTEGER NOT NULL,
    timestamp   TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS game_scores (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id    INTEGER NOT NULL REFERENCES matches(match_id),
    turn        INTEGER NOT NULL,
    beatmap_id  INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    username    TEXT,
    team_index  INTEGER,
    score       INTEGER NOT NULL,
    accuracy    REAL NOT NULL,
    max_combo   INTEGER NOT NULL,
    mods        TEXT NOT NULL,
    passed      INTEGER NOT NULL,
    perfect     INTEGER NOT NULL DEFAULT 0,
    rank        TEXT
);

CREATE INDEX IF NOT EXISTS idx_game_scores_match ON game_scores (match_id);

CREATE TABLE IF NOT EXISTS users (
    id           INTEGER PRIMARY KEY,
    osu_user_id  INTEGER UNIQUE,
    osu_username TEXT NOT NULL,
    role         TEXT CHECK(role IN ('host','ref')),
    irc_username TEXT,
    irc_password TEXT,
    created_at   INTEGER
);

CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER REFERENCES users(id),
    expires_at INTEGER
);

CREATE TABLE IF NOT EXISTS live_matches (
    match_id        TEXT PRIMARY KEY,
    owner_user_id   INTEGER REFERENCES users(id),
    controller_type TEXT,
    payload_json    TEXT,
    state_json      TEXT,
    bancho_lobby_id INTEGER,
    status          TEXT CHECK(status IN ('pending','running','orphaned','finished','crashed')),
    last_heartbeat  INTEGER,
    created_at      INTEGER,
    updated_at      INTEGER
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version    INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
