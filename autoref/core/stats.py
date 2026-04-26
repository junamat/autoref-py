"""Cross-match statistics over `game_scores` rows.

Pure pandas — fed by `MatchDatabase.get_all_scores()` (or any equivalent DataFrame).

A "score predicate" decides which rows count toward the population for a given
metric. Two stock predicates are provided; pass any callable(row_dict) -> bool.
"""
from __future__ import annotations

from typing import Callable, Mapping

import pandas as pd


ScorePredicate = Callable[[Mapping], bool]


def include_all(row: Mapping) -> bool:
    """Default: keep every row."""
    return True


def exclude_failed(row: Mapping) -> bool:
    """Drop rows where the player failed (passed == 0/False)."""
    return bool(row.get("passed"))


_LEADERBOARD_COLUMNS = ["user_id", "username", "maps_played", "z_sum"]


def z_sum_leaderboard(
    scores: pd.DataFrame,
    *,
    include: ScorePredicate = include_all,
) -> pd.DataFrame:
    """Per-player Z-Sum across every beatmap_id present in `scores`.

    Z per row = (score − mean_of_map) / std_of_map. When std is 0 (all players
    tied on a map, or only one player on that map) Z is defined as 0.

    Multiple scores on the same map by the same player are reduced to their best
    *after* the predicate filter — so excluding failed runs and then keeping the
    highest passed score works correctly.
    """
    if scores.empty:
        return pd.DataFrame(columns=_LEADERBOARD_COLUMNS)

    df = scores.loc[scores.apply(include, axis=1)].copy()
    if df.empty:
        return pd.DataFrame(columns=_LEADERBOARD_COLUMNS)

    # Best score per (player, map) — qualifier convention with multiple runs.
    df = (df.sort_values("score", ascending=False)
            .drop_duplicates(subset=["user_id", "beatmap_id"]))

    map_stats = df.groupby("beatmap_id")["score"].agg(["mean", "std"])
    df = df.join(map_stats, on="beatmap_id")
    df["z"] = (df["score"] - df["mean"]) / df["std"]
    df["z"] = df["z"].fillna(0.0)  # std=0 (or NaN) → Z=0

    out = (df.groupby("user_id")
             .agg(username=("username", "last"),
                  maps_played=("beatmap_id", "nunique"),
                  z_sum=("z", "sum"))
             .reset_index()
             .sort_values("z_sum", ascending=False)
             .reset_index(drop=True))
    return out[_LEADERBOARD_COLUMNS]
