"""Shared prep/finish helpers used by all leaderboard algorithms."""
from __future__ import annotations

import pandas as pd

from .predicates import ScorePredicate

_BASE_COLUMNS = ["user_id", "username", "maps_played"]


def _prep(scores: pd.DataFrame, include: ScorePredicate) -> pd.DataFrame | None:
    """Filter, deduplicate to best score per (player, map). Returns None if empty."""
    if scores.empty:
        return None
    df = scores.loc[scores.apply(include, axis=1)].copy()
    if df.empty:
        return None
    return (df.sort_values("score", ascending=False)
              .drop_duplicates(subset=["user_id", "beatmap_id"]))


def _fill_missing_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Fill missing (player, map) combinations with score=0."""
    all_users = df["user_id"].unique()
    all_maps = df["beatmap_id"].unique()
    full_index = pd.MultiIndex.from_product([all_users, all_maps], names=["user_id", "beatmap_id"])

    complete = pd.DataFrame(index=full_index).reset_index()
    df = complete.merge(df, on=["user_id", "beatmap_id"], how="left")
    df["score"] = df["score"].fillna(0)
    df["username"] = df.groupby("user_id")["username"].ffill().bfill()

    return df


def _empty(metric_col: str) -> pd.DataFrame:
    return pd.DataFrame(columns=_BASE_COLUMNS + [metric_col])


def _finish(df: pd.DataFrame, group_col: str, metric_col: str, ascending: bool, aggregate: str = "sum") -> pd.DataFrame:
    agg_func = "mean" if aggregate == "mean" else "sum"
    out = (df.groupby("user_id")
             .agg(username=(group_col, "last"),
                  maps_played=("beatmap_id", "nunique"),
                  **{metric_col: (metric_col, agg_func)})
             .reset_index()
             .sort_values(metric_col, ascending=ascending)
             .reset_index(drop=True))
    return out[_BASE_COLUMNS + [metric_col]]
