from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import pandas as pd
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from ._common import _build_map_code_lookup, _build_map_order_lookup, predicate_for

if TYPE_CHECKING:
    from ...server import WebServer

logger = logging.getLogger(__name__)


def register(app: FastAPI, server: "WebServer") -> None:
    @app.get("/api/stats")
    async def api_stats(method: str = "zscore", count_failed: bool = True, aggregate: str = "sum",
                        pool_id: str | None = None, round_name: str | None = None):
        from ....core.stats import METHODS, PP_METHODS, leaderboard_async
        if method not in METHODS:
            return JSONResponse({"error": f"unknown method: {method}"}, status_code=400)
        if aggregate not in ("sum", "mean"):
            return JSONResponse({"error": "aggregate must be 'sum' or 'mean'"}, status_code=400)
        predicate = predicate_for(count_failed)
        if method in PP_METHODS:
            all_scores_for_lb = server.db.get_all_scores(pool_id=pool_id, round_name=round_name)
            leaderboard = await leaderboard_async(all_scores_for_lb, method=method,
                                                  include=predicate, aggregate=aggregate,
                                                  db=server.db)
        else:
            leaderboard = server.db.get_leaderboard(method=method, include=predicate, aggregate=aggregate,
                                                    pool_id=pool_id, round_name=round_name)
        map_stats   = server.db.get_map_stats(pool_id=pool_id, round_name=round_name)
        map_breakdown = server.db.get_map_action_breakdown(pool_id=pool_id, round_name=round_name)
        all_scores  = server.db.get_all_scores(pool_id=pool_id, round_name=round_name)

        avg_by_map: dict = {}
        acc_by_map: dict = {}
        if not all_scores.empty:
            filtered = all_scores.loc[all_scores.apply(predicate, axis=1)]
            if not filtered.empty:
                avg_by_map = (
                    filtered.groupby("beatmap_id")["score"].mean()
                    .round(0).astype(int).to_dict()
                )
                acc_by_map = (
                    filtered.groupby("beatmap_id")["accuracy"].mean()
                    .round(4).to_dict()
                )

        pool_rows: dict = {}
        for _, row in map_stats.iterrows():
            bid = int(row["beatmap_id"])
            pool_rows.setdefault(bid, {})
            pool_rows[bid][row["step"]] = int(row["count"])

        split_by_bid: dict = {}
        for _, row in map_breakdown.iterrows():
            bid = int(row["beatmap_id"])
            split_by_bid[bid] = {
                "picks_while_protected": int(row["picks_while_protected"]),
                "protect_only":          int(row["protect_only"]),
            }

        code_by_bid = _build_map_code_lookup()
        order_by_bid = _build_map_order_lookup()
        mappool = [
            {
                "beatmap_id":  bid,
                "name":        code_by_bid.get(bid),
                "pool_order":  order_by_bid.get(bid, 99999),
                "picks":    counts.get("PICK", 0),
                "bans":     counts.get("BAN", 0),
                "protects": counts.get("PROTECT", 0),
                "protects_picked": split_by_bid.get(bid, {}).get("picks_while_protected", 0),
                "protects_unused": split_by_bid.get(bid, {}).get("protect_only", 0),
                "avg_score":     avg_by_map.get(bid),
                "avg_acc":       acc_by_map.get(bid),
            }
            for bid, counts in pool_rows.items()
        ]

        _, ascending = METHODS[method]
        metric_col = leaderboard.columns[-1]

        leaderboard_rows = leaderboard.to_dict(orient="records")
        if not all_scores.empty and leaderboard_rows:
            filt = all_scores.loc[all_scores.apply(predicate, axis=1)]
            if not filt.empty:
                per_player = (
                    filt.groupby("user_id")
                        .agg(avg_score=("score", "mean"),
                             avg_acc=("accuracy", "mean"))
                        .to_dict(orient="index")
                )
                best_idx = filt.groupby("user_id")["score"].idxmax()
                best_rows = filt.loc[best_idx].set_index("user_id")
                for r in leaderboard_rows:
                    uid = r["user_id"]
                    agg = per_player.get(uid, {})
                    r["avg_score"] = round(agg.get("avg_score", 0))
                    r["avg_acc"] = round(agg.get("avg_acc", 0), 4)
                    if uid in best_rows.index:
                        b = best_rows.loc[uid]
                        bid = int(b["beatmap_id"])
                        r["best"] = {
                            "beatmap_id": bid,
                            "name":       code_by_bid.get(bid),
                            "score":      int(b["score"]),
                            "accuracy":   round(float(b["accuracy"]), 4),
                            "rank":       (b["rank"] if pd.notna(b["rank"]) else None),
                            "mods":       (json.loads(b["mods"]) if pd.notna(b["mods"]) and b["mods"] else []),
                        }

        total_maps = len(mappool)
        return JSONResponse({
            "methods":    [{"key": k, "label": v[0]} for k, v in METHODS.items()],
            "method":     method,
            "ascending":  ascending,
            "metric_col": metric_col,
            "total_maps": total_maps,
            "leaderboard": leaderboard_rows,
            "mappool":     mappool,
        })
