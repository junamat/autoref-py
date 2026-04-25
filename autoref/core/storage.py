import json
import sqlite3
from pathlib import Path

import pandas as pd


_SCHEMA = """
CREATE TABLE IF NOT EXISTS matches (
    match_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ruleset_vs        INTEGER NOT NULL,
    gamemode          TEXT NOT NULL,
    win_condition     TEXT NOT NULL,
    best_of           INTEGER NOT NULL DEFAULT 1,
    bans_per_team     TEXT NOT NULL DEFAULT '0',      -- JSON: int or list[int]
    protects_per_team TEXT NOT NULL DEFAULT '0',      -- JSON: int or list[int]
    winner_team       TEXT
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
"""


class MatchDatabase:
    def __init__(self, path: str | Path = "matches.db"):
        self._conn = sqlite3.connect(str(path))
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def save_match(self, match: "Match", winner_team_index: int | None = None) -> int:
        winner_name = None
        if winner_team_index is not None:
            winner_name = match.teams[winner_team_index].name

        cursor = self._conn.execute(
            "INSERT INTO matches (ruleset_vs, gamemode, win_condition, best_of, bans_per_team, protects_per_team, winner_team) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                match.ruleset.vs,
                match.ruleset.gamemode.name_api,
                match.ruleset.win_condition.name,
                match.ruleset.best_of,
                json.dumps(match.ruleset.bans_per_team),
                json.dumps(match.ruleset.protects_per_team),
                winner_name,
            ),
        )
        match_id = cursor.lastrowid

        for i, team in enumerate(match.teams):
            self._conn.execute(
                "INSERT INTO match_teams VALUES (?, ?, ?)",
                (match_id, i, team.name),
            )

        if not match.match_status.empty:
            actions = match.match_status.copy()
            actions["match_id"] = match_id
            actions["timestamp"] = actions["timestamp"].astype(str)
            actions.to_sql("match_actions", self._conn, if_exists="append", index=False)

        self._conn.commit()
        match.match_id = match_id
        return match_id

    def get_match_history(self) -> pd.DataFrame:
        return pd.read_sql("SELECT * FROM matches ORDER BY created_at DESC", self._conn)

    def get_map_stats(self) -> pd.DataFrame:
        return pd.read_sql(
            """
            SELECT
                beatmap_id,
                step,
                COUNT(*) AS count
            FROM match_actions
            GROUP BY beatmap_id, step
            ORDER BY beatmap_id, step
            """,
            self._conn,
        )

    def get_team_stats(self) -> pd.DataFrame:
        return pd.read_sql(
            """
            SELECT
                t.team_name,
                COUNT(DISTINCT t.match_id) AS matches_played,
                COUNT(DISTINCT CASE WHEN m.winner_team = t.team_name THEN t.match_id END) AS wins
            FROM match_teams t
            JOIN matches m ON t.match_id = m.match_id
            GROUP BY t.team_name
            ORDER BY wins DESC
            """,
            self._conn,
        )
