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
                    " score, accuracy, max_combo, mods, passed, perfect, rank, "
                    " nmiss, n50, n100, n300, ngeki, nkatu) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        match_id, turn, beatmap_id,
                        s["user_id"], s.get("username"), s.get("team_index"),
                        int(round(adj)), s["accuracy"], s["max_combo"],
                        json.dumps(s.get("mods", [])),
                        int(bool(s["passed"])),
                        int(bool(s.get("perfect", False))),
                        s.get("rank"),
                        int(s.get("nmiss", 0)),
                        int(s.get("n50", 0)),
                        int(s.get("n100", 0)),
                        int(s.get("n300", 0)),
                        int(s.get("ngeki", 0)),
                        int(s.get("nkatu", 0)),
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

    def score_turn_totals(self, *, pool_id: str | None = None,
                           round_name: str | None = None) -> pd.DataFrame:
        clause, params = match_filter(pool_id, round_name, alias="g")
        filt = f"WHERE {clause}" if clause else ""
        return pd.read_sql(
            sql("scores.score_turn_totals").format(filter=filt),
            self._conn, params=params,
        )

    def map_team_scores(self, *, pool_id: str | None = None,
                        round_name: str | None = None) -> pd.DataFrame:
        clause, params = match_filter(pool_id, round_name, alias="g")
        filt = f"WHERE {clause}" if clause else ""
        return pd.read_sql(
            sql("scores.map_team_scores").format(filter=filt),
            self._conn, params=params,
        )

    def team_pool_scores(self, *, pool_id: str | None = None,
                         round_name: str | None = None) -> pd.DataFrame:
        clause, params = match_filter(pool_id, round_name, alias="g")
        filt = f"WHERE {clause}" if clause else ""
        return pd.read_sql(
            sql("scores.team_pool_scores").format(filter=filt),
            self._conn, params=params,
        )

    def scores_with_round(self, *, pool_id: str | None = None,
                          round_name: str | None = None) -> pd.DataFrame:
        clause, params = match_filter(pool_id, round_name, alias="g")
        filt = f"WHERE {clause}" if clause else ""
        return pd.read_sql(
            sql("scores.scores_with_round").format(filter=filt),
            self._conn, params=params,
        )

    def delete_score(self, score_id: int) -> bool:
        cursor = self._conn.execute("DELETE FROM game_scores WHERE id = ?", (score_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    def insert_single_score(self, match_id: int, turn: int, beatmap_id: int,
                            user_id: int, username: str | None, team_index: int | None,
                            score: int, accuracy: float, max_combo: int,
                            mods: list[str], passed: bool, perfect: bool,
                            rank: str | None, nmiss: int, n50: int, n100: int,
                            n300: int, ngeki: int, nkatu: int) -> int:
        cursor = self._conn.execute(
            "INSERT INTO game_scores "
            "(match_id, turn, beatmap_id, user_id, username, team_index, "
            " score, accuracy, max_combo, mods, passed, perfect, rank, "
            " nmiss, n50, n100, n300, ngeki, nkatu) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                match_id, turn, beatmap_id,
                user_id, username, team_index,
                score, accuracy, max_combo,
                json.dumps(mods),
                int(bool(passed)),
                int(bool(perfect)),
                rank,
                nmiss, n50, n100, n300, ngeki, nkatu,
            ),
        )
        self._conn.commit()
        return cursor.lastrowid
