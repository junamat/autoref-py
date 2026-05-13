CREATE TABLE users_new (
    id           INTEGER PRIMARY KEY,
    osu_user_id  INTEGER UNIQUE,
    osu_username TEXT NOT NULL,
    role         TEXT CHECK(role IN ('host','ref','player')),
    irc_username TEXT,
    irc_password TEXT,
    created_at   INTEGER
);
INSERT INTO users_new SELECT * FROM users;
DROP TABLE users;
ALTER TABLE users_new RENAME TO users
