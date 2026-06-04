from __future__ import annotations

import sqlite3

import pandas as pd

from ..loader import sql
from .base import match_filter


class ActionRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def insert_actions(self, match_id: int, match_status: pd.DataFrame) -> None:
        if match_status.empty:
            return
        actions = match_status.copy()
        actions["match_id"] = match_id
        actions["timestamp"] = actions["timestamp"].astype(str)
        actions.to_sql("match_actions", self._conn, if_exists="append", index=False)

    def pick_actions(self, *, pool_id: str | None = None,
                     round_name: str | None = None) -> pd.DataFrame:
        clause, params = match_filter(pool_id, round_name, alias="a")
        filt = f"AND {clause}" if clause else ""
        return pd.read_sql(
            sql("actions.pick_actions").format(filter=filt),
            self._conn, params=params,
        )

    def map_stats(self, *, pool_id: str | None = None,
                  round_name: str | None = None) -> pd.DataFrame:
        clause, params = match_filter(pool_id, round_name)
        filt = f"WHERE {clause}" if clause else ""
        return pd.read_sql(
            sql("actions.map_stats").format(filter=filt),
            self._conn, params=params,
        )

    def map_action_breakdown(self, *, pool_id: str | None = None,
                              round_name: str | None = None) -> pd.DataFrame:
        clause, params = match_filter(pool_id, round_name)
        filt = f"WHERE {clause}" if clause else ""
        return pd.read_sql(
            sql("actions.map_action_breakdown").format(filter=filt),
            self._conn, params=params,
        )

    def pick_win_rates(self, *, pool_id: str | None = None,
                       round_name: str | None = None) -> pd.DataFrame:
        clause, params = match_filter(pool_id, round_name, alias="a")
        filt = f"AND {clause}" if clause else ""
        return pd.read_sql(
            sql("actions.pick_win_rates").format(filter=filt),
            self._conn, params=params,
        )

    def first_picks(self, *, pool_id: str | None = None,
                    round_name: str | None = None) -> pd.DataFrame:
        clause, params = match_filter(pool_id, round_name, alias="a")
        filt = f"AND {clause}" if clause else ""
        return pd.read_sql(
            sql("actions.first_picks").format(filter=filt),
            self._conn, params=params,
        )

    def all_actions_ordered(self, *, pool_id: str | None = None,
                            round_name: str | None = None) -> pd.DataFrame:
        clause, params = match_filter(pool_id, round_name, alias="a")
        filt = f"WHERE {clause}" if clause else ""
        return pd.read_sql(
            sql("actions.all_actions_ordered").format(filter=filt),
            self._conn, params=params,
        )
