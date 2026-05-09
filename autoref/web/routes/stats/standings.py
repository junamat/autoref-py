from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, cast

import pandas as pd
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from ._common import _build_map_code_lookup, _build_map_order_lookup, predicate_for

if TYPE_CHECKING:
    from ...server import WebServer

logger = logging.getLogger(__name__)


def register(app: FastAPI, server: "WebServer") -> None:
    @app.get("/api/stats/standings")
    async def api_stats_standings(count_failed: bool = True,
                                  pool_id: str | None = None,
                                  round_name: str | None = None):
        """Per-map top players and team standings.

        Returns:
          maps: list of {beatmap_id, name, players: [{rank, user_id, username,
                score, accuracy, z, mods, rank_grade}], team_totals: [{team_name,
                total_score, avg_z}]}
          has_teams: bool — True when team_index data is present
        """
        predicate = predicate_for(count_failed)
        scores = server.db.get_all_scores(pool_id=pool_id, round_name=round_name)
        code_by_bid = _build_map_code_lookup()

        if scores.empty:
            return JSONResponse({"maps": [], "has_teams": False})

        df = scores.loc[scores.apply(predicate, axis=1)].copy()
        if df.empty:
            return JSONResponse({"maps": [], "has_teams": False})

        df = df.sort_values("score", ascending=False).drop_duplicates(
            subset=["user_id", "beatmap_id"]
        )

        map_stats = df.groupby("beatmap_id")["score"].agg(["mean", "std"])
        df = df.join(map_stats, on="beatmap_id")
        df["z"] = ((df["score"] - df["mean"]) / df["std"]).fillna(0.0)

        has_teams = df["team_name"].notna().any() if "team_name" in df.columns else False

        maps_out = []
        for bid, grp in df.groupby("beatmap_id"):
            top = grp.sort_values("score", ascending=False)
            players = []
            for rank_i, (_, r) in enumerate(top.iterrows(), 1):
                mods = json.loads(r["mods"]) if pd.notna(r["mods"]) and r["mods"] else []
                players.append({
                    "rank":       rank_i,
                    "user_id":    int(r["user_id"]),
                    "username":   r["username"],
                    "score":      int(r["score"]),
                    "accuracy":   round(float(r["accuracy"]), 4),
                    "z":          round(float(r["z"]), 3),
                    "mods":       mods,
                    "rank_grade": (r["rank"] if pd.notna(r["rank"]) else None),
                })

            team_totals = []
            if has_teams:
                for tname, tgrp in grp.groupby("team_name"):
                    if pd.isna(tname):
                        continue
                    team_totals.append({
                        "team_name":   str(tname),
                        "total_score": int(tgrp["score"].sum()),
                        "avg_z":       round(float(tgrp["z"].mean()), 3),
                    })
                team_totals.sort(key=lambda t: -cast(int, t["total_score"]))

            maps_out.append({
                "beatmap_id":  int(bid),
                "name":        code_by_bid.get(int(bid)),
                "players":     players,
                "team_totals": team_totals,
            })

        map_order = _build_map_order_lookup()
        map_stats_df = server.db.get_map_stats(pool_id=pool_id, round_name=round_name)
        pick_counts = {
            int(row["beatmap_id"]): int(row["count"])
            for _, row in map_stats_df.iterrows()
            if row["step"] == "PICK"
        }
        maps_out.sort(key=lambda m: (
            map_order.get(cast(int, m["beatmap_id"]), 99999),
            -pick_counts.get(cast(int, m["beatmap_id"]), 0),
        ))

        return JSONResponse({"maps": maps_out, "has_teams": bool(has_teams)})
