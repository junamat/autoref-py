from __future__ import annotations

import sqlite3
import time


class LiveRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert(self, match_id: str, *, owner_user_id: int | None = None,
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

    def update_status(self, match_id: str, status: str) -> None:
        now = int(time.time())
        self._conn.execute(
            "UPDATE live_matches SET status = ?, updated_at = ? WHERE match_id = ?",
            (status, now, match_id),
        )
        self._conn.commit()

    def get_orphaned(self) -> list[dict]:
        cols = [r[1] for r in self._conn.execute(
            "PRAGMA table_info(live_matches)"
        ).fetchall()]
        rows = self._conn.execute(
            "SELECT * FROM live_matches WHERE status IN ('running', 'orphaned')"
        ).fetchall()
        return [dict(zip(cols, row)) for row in rows]

    def prune_finished(self, *, days: int = 7) -> int:
        cutoff = int(time.time()) - days * 86400
        cur = self._conn.execute(
            "DELETE FROM live_matches WHERE status = 'finished' AND updated_at < ?",
            (cutoff,),
        )
        self._conn.commit()
        return cur.rowcount
