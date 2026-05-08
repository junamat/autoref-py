import json
import os
import sqlite3
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from .models import Match


_SCHEMA = """
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
    bans_per_team     TEXT NOT NULL DEFAULT '0',      -- JSON: int or list[int]
    protects_per_team TEXT NOT NULL DEFAULT '0',      -- JSON: int or list[int]
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
    mods        TEXT NOT NULL,                          -- JSON list[str]
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
"""


class MatchDatabase:
    def __init__(self, path: str | Path = "matches.db"):
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA)
        self._migrate()
        _p = Path(str(path))
        if _p.exists():
            os.chmod(_p, 0o600)

    def _migrate(self) -> None:
        """Add columns introduced after the original schema. Cheap idempotent ALTERs."""
        existing = {row[1] for row in self._conn.execute("PRAGMA table_info(matches)")}
        for col, decl in (("pool_id", "TEXT"), ("round_name", "TEXT"), ("tb_beatmap_id", "INTEGER")):
            if col not in existing:
                self._conn.execute(f"ALTER TABLE matches ADD COLUMN {col} {decl}")

        existing_gs = {row[1] for row in self._conn.execute("PRAGMA table_info(game_scores)")}
        for col, decl in (("pp", "REAL"), ("pp_version", "TEXT")):
            if col not in existing_gs:
                self._conn.execute(f"ALTER TABLE game_scores ADD COLUMN {col} {decl}")
        self._conn.commit()

    # -------------------------------------------------------------- pp persist

    def update_pp_bulk(self, updates: list[tuple[int, float | None, str | None]]) -> int:
        """Persist computed pp values + the rosu-pp version that produced them.

        Each tuple is (game_scores.id, pp, pp_version). Rows where pp is None
        are skipped (failed compute → keep NULL so a future call can retry).
        Returns the number of rows updated.
        """
        keepers = [
            (float(pp), (str(ver) if ver is not None else None), int(sid))
            for sid, pp, ver in updates if pp is not None
        ]
        if not keepers:
            return 0
        self._conn.executemany(
            "UPDATE game_scores SET pp = ?, pp_version = ? WHERE id = ?",
            keepers,
        )
        self._conn.commit()
        return len(keepers)

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

        tb_beatmap_id = None
        try:
            for pm in match.pool.flatten():
                if getattr(pm, "is_tiebreaker", False):
                    tb_beatmap_id = int(pm.beatmap_id)
                    break
        except Exception:
            tb_beatmap_id = None

        cursor = self._conn.execute(
            "INSERT INTO matches "
            "(ruleset_vs, gamemode, win_condition, best_of, bans_per_team, "
            " protects_per_team, winner_team, pool_id, round_name, tb_beatmap_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                match.ruleset.vs,
                match.ruleset.gamemode.name_api,
                match.ruleset.win_condition.name,
                match.ruleset.best_of,
                json.dumps(match.ruleset.bans_per_team),
                json.dumps(match.ruleset.protects_per_team),
                winner_name,
                getattr(match, "pool_id", None),
                getattr(match, "round_name", None),
                tb_beatmap_id,
            ),
        )
        match_id = cursor.lastrowid
        assert match_id is not None

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

        # Resolve effective per-mod multipliers for each beatmap in this match.
        from .utils import apply_score_multiplier
        ruleset_mults = getattr(match.ruleset, "score_multipliers", None)
        mults_by_bid: dict[int, dict[str, float]] = {}
        try:
            for pm in match.pool.flatten():
                mults_by_bid[int(pm.beatmap_id)] = pm.effective_multipliers(ruleset_mults)
        except Exception:
            mults_by_bid = {}

        # API-enriched per-player scores keyed by turn.
        for turn, beatmap_id, scores in getattr(match, "game_scores", []):
            mult = mults_by_bid.get(int(beatmap_id))
            for s in scores:
                raw_score = s["score"]
                adj = apply_score_multiplier(raw_score, s.get("mods", []), mult)
                self._conn.execute(
                    "INSERT INTO game_scores "
                    "(match_id, turn, beatmap_id, user_id, username, team_index, "
                    " score, accuracy, max_combo, mods, passed, perfect, rank) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        match_id, turn, beatmap_id,
                        s["user_id"], s.get("username"), s.get("team_index"),
                        int(round(adj)), s["accuracy"], s["max_combo"],
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

    def _match_filter(self, pool_id: str | None, round_name: str | None,
                      alias: str = "") -> tuple[str, list]:
        """Build a `match_id IN (…)` subquery clause restricting to matches with
        the given pool / round. Returns ('', []) when no filter is requested.

        Both args are optional and combine with AND. None or empty means "any".
        `alias` qualifies the outer `match_id` column (e.g. 'a' → 'a.match_id')
        when the surrounding query joins multiple tables that share that name.
        """
        conds, params = [], []
        if pool_id:
            conds.append("pool_id = ?")
            params.append(pool_id)
        if round_name:
            conds.append("round_name = ?")
            params.append(round_name)
        if not conds:
            return "", []
        col = f"{alias}.match_id" if alias else "match_id"
        return f" {col} IN (SELECT match_id FROM matches WHERE {' AND '.join(conds)}) ", params

    def get_filter_options(self) -> dict:
        """Distinct (pool_id, round_name) combinations seen in the DB, plus the
        list of pool_ids and round_names individually. Used to populate the
        /stats filter UI.
        """
        rows = self._conn.execute(
            "SELECT DISTINCT pool_id, round_name FROM matches "
            "WHERE pool_id IS NOT NULL OR round_name IS NOT NULL"
        ).fetchall()
        combos = [{"pool_id": p, "round_name": r} for p, r in rows]
        pools  = sorted({p for p, _ in rows if p})
        rounds = sorted({r for _, r in rows if r})
        return {"combos": combos, "pools": pools, "rounds": rounds}

    def get_pick_actions(self, *, pool_id: str | None = None,
                          round_name: str | None = None) -> pd.DataFrame:
        """All PICK events with their match context. Columns: match_id, turn,
        team_index (the team that picked), beatmap_id, round_name."""
        clause, params = self._match_filter(pool_id, round_name, alias="a")
        where = f"AND {clause}" if clause else ""
        return pd.read_sql(
            f"""
            SELECT a.match_id, a.turn, a.team_index AS picker_team,
                   a.beatmap_id, m.round_name
            FROM match_actions a
            LEFT JOIN matches m ON m.match_id = a.match_id
            WHERE a.step = 'PICK' {where}
            ORDER BY a.match_id, a.turn
            """,
            self._conn,
            params=params,
        )

    def get_map_stats(self, *, pool_id: str | None = None,
                      round_name: str | None = None) -> pd.DataFrame:
        clause, params = self._match_filter(pool_id, round_name)
        where = f"WHERE {clause}" if clause else ""
        return pd.read_sql(
            f"""
            SELECT
                beatmap_id,
                step,
                COUNT(*) AS count
            FROM match_actions
            {where}
            GROUP BY beatmap_id, step
            ORDER BY beatmap_id, step
            """,
            self._conn,
            params=params,
        )

    def get_map_action_breakdown(self, *, pool_id: str | None = None,
                                  round_name: str | None = None) -> pd.DataFrame:
        """Per-beatmap counts that distinguish protect→pick overlap from
        protect-without-pick. Used by the pick/ban/protect heat plot.

        Columns: beatmap_id, bans, picks, picks_while_protected, protect_only.
        - picks_while_protected: picks of a map in a match where the same map
          was also protected at least once.
        - protect_only: protect events on maps that were NOT subsequently
          picked in the same match.
        """
        clause, params = self._match_filter(pool_id, round_name)
        where = f"WHERE {clause}" if clause else ""
        return pd.read_sql(
            f"""
            WITH per_match_map AS (
                SELECT
                    match_id, beatmap_id,
                    SUM(CASE WHEN step = 'PICK'    THEN 1 ELSE 0 END) AS picks,
                    SUM(CASE WHEN step = 'BAN'     THEN 1 ELSE 0 END) AS bans,
                    SUM(CASE WHEN step = 'PROTECT' THEN 1 ELSE 0 END) AS protects
                FROM match_actions
                {where}
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
            params=params,
        )

    def get_game_scores(self, match_id: int) -> pd.DataFrame:
        return pd.read_sql(
            "SELECT * FROM game_scores WHERE match_id = ? ORDER BY turn, score DESC",
            self._conn,
            params=(match_id,),
        )

    def get_all_scores(self, *, pool_id: str | None = None,
                       round_name: str | None = None) -> pd.DataFrame:
        """Every game_scores row across every match — input for cross-match stats.
        Optionally restrict to matches matching pool_id / round_name.
        Includes team_name joined from match_teams on (match_id, team_index).
        """
        clause, params = self._match_filter(pool_id, round_name, alias="g")
        where = f"WHERE {clause}" if clause else ""
        return pd.read_sql(
            f"""
            SELECT g.*, mt.team_name, m.tb_beatmap_id
            FROM game_scores g
            LEFT JOIN match_teams mt
                ON mt.match_id = g.match_id AND mt.team_index = g.team_index
            LEFT JOIN matches m
                ON m.match_id = g.match_id
            {where}
            """,
            self._conn, params=params)

    def get_leaderboard(self, *, method: str = "zscore", include=None,
                        aggregate: str = "sum",
                        pool_id: str | None = None,
                        round_name: str | None = None) -> pd.DataFrame:
        """Cross-match leaderboard. `method` selects the calculation strategy;
        `include` is a row predicate (defaults to include_all);
        `aggregate` is "sum" or "mean" for per-map metric aggregation."""
        from .stats import include_all, leaderboard
        return leaderboard(self.get_all_scores(pool_id=pool_id, round_name=round_name),
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

    # --------------------------------------------------------- live_matches

    def upsert_live_match(self, match_id: str, *, owner_user_id: int | None = None,
                          controller_type: str | None = None,
                          payload_json: str | None = None,
                          state_json: str | None = None,
                          bancho_lobby_id: int | None = None,
                          status: str = "running") -> None:
        now = int(time.time())
        self._conn.execute(
            """
            INSERT INTO live_matches
                (match_id, owner_user_id, controller_type, payload_json,
                 state_json, bancho_lobby_id, status, last_heartbeat, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(match_id) DO UPDATE SET
                state_json      = coalesce(excluded.state_json, state_json),
                bancho_lobby_id = coalesce(excluded.bancho_lobby_id, bancho_lobby_id),
                status          = excluded.status,
                last_heartbeat  = excluded.last_heartbeat,
                updated_at      = excluded.updated_at
            """,
            (match_id, owner_user_id, controller_type, payload_json,
             state_json, bancho_lobby_id, status, now, now, now),
        )
        self._conn.commit()

    def update_live_match_status(self, match_id: str, status: str) -> None:
        now = int(time.time())
        self._conn.execute(
            "UPDATE live_matches SET status = ?, updated_at = ? WHERE match_id = ?",
            (status, now, match_id),
        )
        self._conn.commit()

    def get_orphaned_live_matches(self) -> list[dict]:
        cols = [r[1] for r in self._conn.execute("PRAGMA table_info(live_matches)").fetchall()]
        rows = self._conn.execute(
            "SELECT * FROM live_matches WHERE status IN ('running', 'orphaned')"
        ).fetchall()
        return [dict(zip(cols, row)) for row in rows]

    def prune_finished_live_matches(self, *, days: int = 7) -> int:
        cutoff = int(time.time()) - days * 86400
        cur = self._conn.execute(
            "DELETE FROM live_matches WHERE status = 'finished' AND updated_at < ?",
            (cutoff,),
        )
        self._conn.commit()
        return cur.rowcount
