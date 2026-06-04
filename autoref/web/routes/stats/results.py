from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from ._common import _build_map_code_lookup, _build_map_mod_group_lookup, _build_map_order_lookup, predicate_for

if TYPE_CHECKING:
    from ...server import WebServer


def register(app: FastAPI, server: "WebServer") -> None:
    @app.get("/api/stats/results")
    async def api_stats_results(count_failed: bool = True,
                                pool_id: str | None = None,
                                round_name: str | None = None,
                                method: str = "zscore",
                                aggregate: str = "sum"):
        """Qualifiers-style team×map grid.

        Returns:
          teams: [{team_name, maps: {beatmap_id: {score, z, rank}}, total_z, avg_z}]
          map_order: [beatmap_id, ...]  — ordered by pool position / pick count
          has_data: bool
        """
        from ....core.stats import METHODS, PP_METHODS, team_leaderboard
        if method not in METHODS:
            return JSONResponse({"error": f"unknown method: {method}"}, status_code=400)
        if method in PP_METHODS:
            return JSONResponse(
                {"error": f"method {method!r} not yet supported on team-level results"},
                status_code=400,
            )
        predicate = predicate_for(count_failed)
        scores = server.db.get_all_scores(pool_id=pool_id, round_name=round_name)
        code_by_bid = _build_map_code_lookup()

        if scores.empty:
            return JSONResponse({"teams": [], "map_order": [], "has_data": False})

        df = scores.loc[scores.apply(predicate, axis=1)].copy()
        if df.empty or "team_name" not in df.columns or df["team_name"].isna().all():
            return JSONResponse({"teams": [], "map_order": [], "has_data": False})

        df = df.sort_values("score", ascending=False).drop_duplicates(
            subset=["user_id", "beatmap_id"]
        )

        team_map = (df.groupby(["team_name", "beatmap_id"])
                      .agg(total_score=("score", "sum"))
                      .reset_index())

        team_map["map_rank"] = team_map.groupby("beatmap_id")["total_score"].rank(
            ascending=False, method="min"
        ).astype(int)

        agg_col = "mean" if aggregate == "mean" else "sum"
        team_lb = team_leaderboard(scores, method=method, include=predicate, aggregate=agg_col)
        metric_label, ascending = METHODS[method]
        metric_col = team_lb.columns[-1]

        teams_dict: dict[str, dict] = {}
        for _, r in team_map.iterrows():
            tname = r["team_name"]
            if pd.isna(tname):
                continue
            if tname not in teams_dict:
                teams_dict[tname] = {"team_name": str(tname), "maps": {}}
            bid = int(r["beatmap_id"])
            teams_dict[tname]["maps"][bid] = {
                "total_score": int(r["total_score"]),
                "map_rank":    int(r["map_rank"]),
            }

        for _, r in team_lb.iterrows():
            tname = r["username"]
            if tname in teams_dict:
                val = float(r[metric_col])
                teams_dict[tname]["total_metric"] = round(val, 3)
                teams_dict[tname]["avg_metric"]   = round(val, 3)

        sort_key = (lambda t: t.get("total_metric", 0)) if ascending \
            else (lambda t: -t.get("total_metric", 0))
        teams_out = sorted(teams_dict.values(), key=sort_key)

        map_order_lookup = _build_map_order_lookup()
        map_stats_df = server.db.get_map_stats(pool_id=pool_id, round_name=round_name)
        pick_counts = {
            int(row["beatmap_id"]): int(row["count"])
            for _, row in map_stats_df.iterrows()
            if row["step"] == "PICK"
        }
        all_bids = sorted(
            df["beatmap_id"].unique(),
            key=lambda b: (map_order_lookup.get(int(b), 99999), -pick_counts.get(int(b), 0))
        )
        import json as _json
        mods_by_bid: dict[int, list[str]] = {}
        for bid, grp in df.groupby("beatmap_id"):
            all_mods = []
            for m in grp["mods"]:
                if _json.loads(m) if m else []:
                    all_mods.extend(_json.loads(m))
            mods_by_bid[int(bid)] = list(set(all_mods))

        pool_mods_by_bid = _build_map_mod_group_lookup()

        map_order = [
            {
                "beatmap_id": int(b),
                "name": code_by_bid.get(int(b)),
                "mods": mods_by_bid.get(int(b), []),
                "pool_mod": pool_mods_by_bid.get(int(b)),
            }
            for b in all_bids
        ]

        return JSONResponse({
            "teams":         teams_out,
            "map_order":     map_order,
            "method":        method,
            "metric_col":    metric_col,
            "metric_label":  metric_label,
            "aggregate":     agg_col,
            "ascending":     ascending,
            "has_data":      True,
        })
