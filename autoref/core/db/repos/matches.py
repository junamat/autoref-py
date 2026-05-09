from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING

import pandas as pd

from ..loader import sql

if TYPE_CHECKING:
    from ...models import Match


class MatchRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save_match_row(self, match: "Match",
                       winner_team_index: int | None = None) -> int:
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
        assert cursor.lastrowid is not None
        return cursor.lastrowid

    def history(self) -> pd.DataFrame:
        return pd.read_sql(sql("matches.history"), self._conn)

    def filter_options(self) -> dict:
        rows = self._conn.execute(sql("matches.filter_options")).fetchall()
        combos = [{"pool_id": p, "round_name": r} for p, r in rows]
        pools  = sorted({p for p, _ in rows if p})
        rounds = sorted({r for _, r in rows if r})
        return {"combos": combos, "pools": pools, "rounds": rounds}

    def context(self, *, pool_id: str | None = None,
                round_name: str | None = None) -> dict:
        from .base import match_filter
        clause_mt, params_mt = match_filter(pool_id, round_name, alias="mt")
        where_mt = f" AND{clause_mt}" if clause_mt else ""
        has_teams: bool = self._conn.execute(
            f"SELECT COUNT(*) FROM match_teams mt WHERE 1=1{where_mt}", params_mt
        ).fetchone()[0] > 0

        clause_ma, params_ma = match_filter(pool_id, round_name, alias="ma")
        where_ma = f" AND{clause_ma}" if clause_ma else ""
        has_bracket: bool = self._conn.execute(
            f"SELECT COUNT(*) FROM match_actions ma"
            f" WHERE ma.step IN ('BAN','PROTECT'){where_ma}",
            params_ma,
        ).fetchone()[0] > 0

        return {"has_teams": has_teams, "has_bracket": has_bracket}
