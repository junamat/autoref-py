from __future__ import annotations

import json
from typing import Any

import pandas as pd

from ..schemas.stats import BestScore, MapPoolRow


def build_mappool_row(
    bid: int,
    counts: dict[str, int],
    split_by_bid: dict[int, dict[str, int]],
    avg_by_map: dict[int, int],
    acc_by_map: dict[int, float],
    code_by_bid: dict[int, str],
    order_by_bid: dict[int, int],
    mods_by_bid: dict[int, list[str]] | None = None,
    play_count_by_map: dict[int, int] | None = None,
) -> MapPoolRow:
    """Build one MapPoolRow from aggregated DB query results."""
    split = split_by_bid.get(bid, {})
    row: MapPoolRow = MapPoolRow(
        beatmap_id=bid,
        name=code_by_bid.get(bid),
        pool_order=order_by_bid.get(bid, 99999),
        picks=counts.get("PICK", 0),
        bans=counts.get("BAN", 0),
        protects=counts.get("PROTECT", 0),
        protects_picked=split.get("picks_while_protected", 0),
        protects_unused=split.get("protect_only", 0),
        avg_score=avg_by_map.get(bid),
        avg_acc=acc_by_map.get(bid),
        play_count=play_count_by_map.get(bid, 0) if play_count_by_map else 0,
    )
    if mods_by_bid and bid in mods_by_bid:
        row["mods"] = mods_by_bid[bid]
    return row


def enrich_leaderboard_rows(
    leaderboard_rows: list[dict[str, Any]],
    all_scores: pd.DataFrame,
    predicate: Any,
    code_by_bid: dict[int, str],
) -> list[dict[str, Any]]:
    """Add avg_score, avg_acc, best fields to raw leaderboard rows."""
    if all_scores.empty or not leaderboard_rows:
        return leaderboard_rows

    filt = all_scores.loc[all_scores.apply(predicate, axis=1)]
    if filt.empty:
        return leaderboard_rows

    per_player = (
        filt.groupby("user_id")
            .agg(avg_score=("score", "mean"), avg_acc=("accuracy", "mean"))
            .to_dict(orient="index")
    )
    best_idx = filt.groupby("user_id")["score"].idxmax()
    best_rows = filt.loc[best_idx].set_index("user_id")

    enriched: list[dict[str, Any]] = []
    for r in leaderboard_rows:
        row = dict(r)
        uid = r["user_id"]
        agg = per_player.get(uid, {})
        row["avg_score"] = round(agg.get("avg_score", 0))
        row["avg_acc"] = round(agg.get("avg_acc", 0), 4)
        if uid in best_rows.index:
            b = best_rows.loc[uid]
            bid = int(b["beatmap_id"])
            row["best"] = BestScore(
                beatmap_id=bid,
                name=code_by_bid.get(bid),
                score=int(b["score"]),
                accuracy=round(float(b["accuracy"]), 4),
                rank=(b["rank"] if pd.notna(b["rank"]) else None),
                mods=(json.loads(b["mods"]) if pd.notna(b["mods"]) and b["mods"] else []),
            )
        enriched.append(row)
    return enriched
