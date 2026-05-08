from __future__ import annotations

import json
import sqlite3

import pandas as pd

from ..loader import sql
from .base import match_filter


class ScoreRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def insert_scores(self, match_id: int,
                      scores_iter: list[tuple[int, int, list[dict]]],
                      mults_by_bid: dict[int, dict[str, float]]) -> None:
        from ...utils import apply_score_multiplier
        for turn, beatmap_id, scores in scores_iter:
            mult = mults_by_bid.get(int(beatmap_id))
            for s in scores:
                adj = apply_score_multiplier(s["score"], s.get("mods", []), mult)
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

    def update_pp_bulk(self, updates: list[tuple[int, float | None, str | None]]) -> int:
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

    def by_match(self, match_id: int) -> pd.DataFrame:
        return pd.read_sql(sql("scores.by_match"), self._conn, params=(match_id,))

    def all_with_team(self, *, pool_id: str | None = None,
                      round_name: str | None = None) -> pd.DataFrame:
        clause, params = match_filter(pool_id, round_name, alias="g")
        filt = f"WHERE {clause}" if clause else ""
        return pd.read_sql(
            sql("scores.all_with_team").format(filter=filt),
            self._conn, params=params,
        )
