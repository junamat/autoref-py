from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from ._common import predicate_for

if TYPE_CHECKING:
    from ...server import WebServer


def register(app: FastAPI, server: "WebServer") -> None:
    @app.get("/api/stats/team_performances")
    async def api_stats_team_performances(count_failed: bool = True,
                                          pool_id: str | None = None,
                                          round_name: str | None = None):
        """Team-level performance table.

        Returns:
          teams: [{team_name, matches_played, wins, avg_z, avg_score,
                   maps_played, win_rate}]
        """
        predicate = predicate_for(count_failed)
        scores = server.db.get_all_scores(pool_id=pool_id, round_name=round_name)

        try:
            team_stats = server.db.get_team_stats()
        except Exception:
            team_stats = pd.DataFrame()

        if scores.empty:
            rows = []
            if not team_stats.empty:
                for _, r in team_stats.iterrows():
                    rows.append({
                        "team_name":     r["team_name"],
                        "matches_played": int(r["matches_played"]),
                        "wins":           int(r["wins"]),
                        "win_rate":       round(int(r["wins"]) / max(int(r["matches_played"]), 1), 3),
                        "avg_z":          None,
                        "avg_score":      None,
                        "maps_played":    0,
                    })
            return JSONResponse({"teams": rows})

        df = scores.loc[scores.apply(predicate, axis=1)].copy()
        if df.empty or "team_name" not in df.columns or df["team_name"].isna().all():
            return JSONResponse({"teams": []})

        df = df.sort_values("score", ascending=False).drop_duplicates(
            subset=["user_id", "beatmap_id"]
        )

        map_stats = df.groupby("beatmap_id")["score"].agg(["mean", "std"])
        df = df.join(map_stats, on="beatmap_id")
        df["z"] = ((df["score"] - df["mean"]) / df["std"]).fillna(0.0)

        team_agg = (df.groupby("team_name")
                      .agg(avg_z=("z", "mean"),
                           avg_score=("score", "mean"),
                           maps_played=("beatmap_id", "nunique"))
                      .reset_index())

        rows = []
        for _, r in team_agg.iterrows():
            tname = r["team_name"]
            if pd.isna(tname):
                continue
            ws_row = team_stats[team_stats["team_name"] == tname] if not team_stats.empty else pd.DataFrame()
            matches = int(ws_row["matches_played"].iloc[0]) if not ws_row.empty else 0
            wins    = int(ws_row["wins"].iloc[0])           if not ws_row.empty else 0
            rows.append({
                "team_name":      str(tname),
                "matches_played": matches,
                "wins":           wins,
                "win_rate":       round(wins / max(matches, 1), 3),
                "avg_z":          round(float(r["avg_z"]), 3),
                "avg_score":      round(float(r["avg_score"])),
                "maps_played":    int(r["maps_played"]),
            })

        rows.sort(key=lambda t: -t["avg_z"])
        return JSONResponse({"teams": rows})
