from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, cast

import pandas as pd
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from ._common import _build_map_code_lookup, predicate_for

if TYPE_CHECKING:
    from ...server import WebServer

logger = logging.getLogger(__name__)


def register(app: FastAPI, server: "WebServer") -> None:
    @app.get("/api/stats/extras")
    async def api_stats_extras(count_failed: bool = True,
                                pool_id: str | None = None,
                                round_name: str | None = None,
                                top_n: int = 20):
        predicate = predicate_for(count_failed)

        scores  = server.db.get_all_scores(pool_id=pool_id, round_name=round_name)
        picks   = server.db.get_pick_actions(pool_id=pool_id, round_name=round_name)
        code_by_bid = _build_map_code_lookup()

        if scores.empty or picks.empty:
            return JSONResponse({
                "closest_maps": [], "biggest_blowouts": [], "biggest_carries": [],
            })

        scores = scores.loc[scores.apply(predicate, axis=1)].copy()
        if scores.empty:
            return JSONResponse({
                "closest_maps": [], "biggest_blowouts": [], "biggest_carries": [],
            })

        picks_key = picks[["match_id", "beatmap_id", "round_name"]].drop_duplicates(
            subset=["match_id", "beatmap_id"]
        )
        pick_scores = scores.merge(
            picks_key, on=["match_id", "beatmap_id"], how="inner"
        )
        if pick_scores.empty:
            return JSONResponse({
                "closest_maps": [], "biggest_blowouts": [], "biggest_carries": [],
            })

        team_totals = (pick_scores
            .groupby(["match_id", "beatmap_id", "round_name",
                      "team_index", "team_name"], dropna=False)
            ["score"].sum()
            .reset_index())
        diffs = []
        for (mid, bid, rnd), grp in team_totals.groupby(
                ["match_id", "beatmap_id", "round_name"], dropna=False):
            if len(grp) != 2:
                continue
            grp = grp.sort_values("team_index")
            a_row, b_row = grp.iloc[0], grp.iloc[1]
            a_score, b_score = int(a_row["score"]), int(b_row["score"])
            if a_score > b_score:
                winner = "a"
            elif b_score > a_score:
                winner = "b"
            else:
                winner = "tie"
            diffs.append({
                "match_id":   int(mid),
                "round_name": rnd if pd.notna(rnd) else None,
                "beatmap_id": int(bid),
                "name":       code_by_bid.get(int(bid)),
                "team_a":     a_score,
                "team_b":     b_score,
                "team_a_name": a_row["team_name"] if pd.notna(a_row["team_name"]) else None,
                "team_b_name": b_row["team_name"] if pd.notna(b_row["team_name"]) else None,
                "winner":     winner,
                "diff":       abs(a_score - b_score),
            })

        closest  = sorted(diffs, key=lambda d: cast(int, d["diff"]))[:top_n]
        blowouts = sorted(diffs, key=lambda d: -cast(int, d["diff"]))[:top_n]

        map_stats = scores.groupby("beatmap_id")["score"].agg(["mean", "std"]).reset_index()
        pick_scores = pick_scores.merge(map_stats, on="beatmap_id", how="left")
        pick_scores["z"] = ((pick_scores["score"] - pick_scores["mean"]) /
                            pick_scores["std"]).fillna(0.0)

        team_z_avg = (pick_scores
            .groupby(["match_id", "beatmap_id", "team_index"])
            ["z"].mean()
            .reset_index().rename(columns={"z": "team_avg_z"}))
        pick_scores = pick_scores.merge(
            team_z_avg, on=["match_id", "beatmap_id", "team_index"]
        )
        pick_scores["carry_z"] = pick_scores["z"] - pick_scores["team_avg_z"]

        top_carry = pick_scores.nlargest(top_n, "carry_z")
        carries = []
        for _, r in top_carry.iterrows():
            bid = int(r["beatmap_id"])
            mods = json.loads(r["mods"]) if pd.notna(r["mods"]) and r["mods"] else []
            carries.append({
                "match_id":   int(r["match_id"]),
                "round_name": r["round_name"],
                "user_id":    int(r["user_id"]),
                "username":   r["username"],
                "beatmap_id": bid,
                "name":       code_by_bid.get(bid),
                "mods":       mods,
                "score":      int(r["score"]),
                "accuracy":   round(float(r["accuracy"]), 4),
                "rank":       (r["rank"] if pd.notna(r["rank"]) else None),
                "z":          round(float(r["z"]), 3),
                "team_avg_z": round(float(r["team_avg_z"]), 3),
                "carry_z":    round(float(r["carry_z"]), 3),
            })

        highest_pp: list = []
        highest_zpp: list = []
        try:
            from ....core.stats import augment_pp
            aug = await augment_pp(pick_scores, db=server.db)
            if "pp" in aug.columns and aug["pp"].notna().any():
                pp_df = aug.dropna(subset=["pp"]).copy()
                pp_top = pp_df.nlargest(top_n, "pp")
                for _, r in pp_top.iterrows():
                    bid = int(r["beatmap_id"])
                    mods = json.loads(r["mods"]) if pd.notna(r["mods"]) and r["mods"] else []
                    highest_pp.append({
                        "match_id":   int(r["match_id"]),
                        "round_name": r["round_name"] if "round_name" in r and pd.notna(r["round_name"]) else None,
                        "user_id":    int(r["user_id"]),
                        "username":   r["username"],
                        "beatmap_id": bid,
                        "name":       code_by_bid.get(bid),
                        "mods":       mods,
                        "score":      int(r["score"]),
                        "accuracy":   round(float(r["accuracy"]), 4),
                        "rank":       (r["rank"] if pd.notna(r["rank"]) else None),
                        "pp":         round(float(r["pp"]), 1),
                    })

                map_pp = pp_df.groupby("beatmap_id")["pp"].agg(["mean", "std"])
                pp_df = pp_df.join(map_pp, on="beatmap_id", rsuffix="_map")
                pp_df["zpp"] = ((pp_df["pp"] - pp_df["mean_map"]) / pp_df["std_map"]).fillna(0.0)
                zpp_top = pp_df.nlargest(top_n, "zpp")
                for _, r in zpp_top.iterrows():
                    bid = int(r["beatmap_id"])
                    mods = json.loads(r["mods"]) if pd.notna(r["mods"]) and r["mods"] else []
                    highest_zpp.append({
                        "match_id":   int(r["match_id"]),
                        "round_name": r["round_name"] if "round_name" in r and pd.notna(r["round_name"]) else None,
                        "user_id":    int(r["user_id"]),
                        "username":   r["username"],
                        "beatmap_id": bid,
                        "name":       code_by_bid.get(bid),
                        "mods":       mods,
                        "score":      int(r["score"]),
                        "accuracy":   round(float(r["accuracy"]), 4),
                        "rank":       (r["rank"] if pd.notna(r["rank"]) else None),
                        "pp":         round(float(r["pp"]), 1),
                        "zpp":        round(float(r["zpp"]), 3),
                    })
        except Exception:
            logger.warning("pp augmentation failed", exc_info=True)

        return JSONResponse({
            "closest_maps":     closest,
            "biggest_blowouts": blowouts,
            "biggest_carries":  carries,
            "highest_pp":       highest_pp,
            "highest_zpp":      highest_zpp,
        })
