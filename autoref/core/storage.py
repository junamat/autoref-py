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
    mods        TEXT NOT NULL,                          -- JSON list[str]
    passed      INTEGER NOT NULL,
    perfect     INTEGER NOT NULL DEFAULT 0,
    rank        TEXT
);
CREATE INDEX IF NOT EXISTS idx_game_scores_match ON game_scores (match_id);
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

        # API-enriched per-player scores keyed by turn.
        for turn, beatmap_id, scores in getattr(match, "game_scores", []):
            for s in scores:
                self._conn.execute(
                    "INSERT INTO game_scores "
                    "(match_id, turn, beatmap_id, user_id, username, team_index, "
                    " score, accuracy, max_combo, mods, passed, perfect, rank) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        match_id, turn, beatmap_id,
                        s["user_id"], s.get("username"), s.get("team_index"),
                        s["score"], s["accuracy"], s["max_combo"],
                        json.dumps(s.get("mods", [])),
                        int(bool(s["passed"])),
                        int(bool(s.get("perfect", False))),
                        s.get("rank"),
                    ),
                )

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

    def get_map_action_breakdown(self) -> pd.DataFrame:
        """Per-beatmap counts that distinguish protect→pick overlap from
        protect-without-pick. Used by the pick/ban/protect heat plot.

        Columns: beatmap_id, bans, picks, picks_while_protected, protect_only.
        - picks_while_protected: picks of a map in a match where the same map
          was also protected at least once.
        - protect_only: protect events on maps that were NOT subsequently
          picked in the same match.
        """
        return pd.read_sql(
            """
            WITH per_match_map AS (
                SELECT
                    match_id, beatmap_id,
                    SUM(CASE WHEN step = 'PICK'    THEN 1 ELSE 0 END) AS picks,
                    SUM(CASE WHEN step = 'BAN'     THEN 1 ELSE 0 END) AS bans,
                    SUM(CASE WHEN step = 'PROTECT' THEN 1 ELSE 0 END) AS protects
                FROM match_actions
                GROUP BY match_id, beatmap_id
            )
            SELECT
                beatmap_id,
                SUM(bans)  AS bans,
                SUM(picks) AS picks,
                SUM(CASE WHEN protects > 0 THEN picks    ELSE 0 END) AS picks_while_protected,
                SUM(CASE WHEN picks    = 0 THEN protects ELSE 0 END) AS protect_only
            FROM per_match_map
            GROUP BY beatmap_id
            ORDER BY beatmap_id
            """,
            self._conn,
        )

    def get_game_scores(self, match_id: int) -> pd.DataFrame:
        return pd.read_sql(
            "SELECT * FROM game_scores WHERE match_id = ? ORDER BY turn, score DESC",
            self._conn,
            params=(match_id,),
        )

    def get_all_scores(self) -> pd.DataFrame:
        """Every game_scores row across every match — input for cross-match stats."""
        return pd.read_sql("SELECT * FROM game_scores", self._conn)

    def get_leaderboard(self, *, method: str = "zscore", include=None, aggregate: str = "sum") -> pd.DataFrame:
        """Cross-match leaderboard. `method` selects the calculation strategy;
        `include` is a row predicate (defaults to include_all);
        `aggregate` is "sum" or "mean" for per-map metric aggregation."""
        from .stats import leaderboard, include_all
        return leaderboard(self.get_all_scores(),
                           method=method,
                           include=include or include_all,
                           aggregate=aggregate)

    def get_z_sum_leaderboard(self, *, include=None) -> pd.DataFrame:
        """Backwards-compat alias for get_leaderboard(method='zscore')."""
        return self.get_leaderboard(method="zscore", include=include)

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
