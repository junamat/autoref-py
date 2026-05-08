from __future__ import annotations

import sqlite3

import pandas as pd

from ..loader import sql


class TeamRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def insert_team(self, match_id: int, idx: int, name: str) -> None:
        self._conn.execute(
            "INSERT INTO match_teams VALUES (?, ?, ?)",
            (match_id, idx, name),
        )

    def stats(self) -> pd.DataFrame:
        return pd.read_sql(sql("teams.stats"), self._conn)
