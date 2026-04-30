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


# Registry: method key → (label, ascending_sort)
METHODS: dict[str, tuple[str, bool]] = {
    "zscore":      ("Z-Score",                  False),
    "avg_score":   ("Average Score",            False),
    "placements":  ("Placements",               True),
    "percentile":  ("Percentile",               False),
    "zipf":        ("Zipf's Law",               False),
    "pct_diff":    ("Percent Difference",       False),
}

_BASE_COLUMNS = ["user_id", "username", "maps_played"]


def leaderboard(
    scores: pd.DataFrame,
    *,
    method: str = "zscore",
    include: ScorePredicate = include_all,
    aggregate: str = "sum",
) -> pd.DataFrame:
    """Unified dispatcher. Returns _BASE_COLUMNS + [metric_col] sorted appropriately.
    
    aggregate: "sum" or "mean" - how to aggregate per-map metrics across maps.
    """
    if method not in METHODS:
        raise ValueError(f"unknown method {method!r}; choose from {list(METHODS)}")

    fn = {
        "zscore":     z_sum_leaderboard,
        "avg_score":  avg_score_leaderboard,
        "placements": avg_placements_leaderboard,
        "percentile": percentile_leaderboard,
        "zipf":       zipf_leaderboard,
        "pct_diff":   pct_diff_leaderboard,
    }[method]
    return fn(scores, include=include, aggregate=aggregate)


# ── shared prep ──────────────────────────────────────────────────────────────

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
    """Fill missing (player, map) combinations with score=0.
    
    Used by methods that need to count missing scores as 0 for individual players.
    """
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


# ── Z-Sum ─────────────────────────────────────────────────────────────────────

def z_sum_leaderboard(
    scores: pd.DataFrame,
    *,
    include: ScorePredicate = include_all,
    aggregate: str = "sum",
) -> pd.DataFrame:
    """Per-player Z-Sum. Z = (score − map_mean) / map_std; std=0 → Z=0.
    
    Missing scores are excluded from calculation (not counted as 0).
    """
    df = _prep(scores, include)
    if df is None:
        return _empty("z_sum")

    map_stats = df.groupby("beatmap_id")["score"].agg(["mean", "std"])
    df = df.join(map_stats, on="beatmap_id")
    df["z_sum"] = ((df["score"] - df["mean"]) / df["std"]).fillna(0.0)
    return _finish(df, "username", "z_sum", ascending=False, aggregate=aggregate)


# ── Average Score ─────────────────────────────────────────────────────────────

def avg_score_leaderboard(
    scores: pd.DataFrame,
    *,
    include: ScorePredicate = include_all,
    aggregate: str = "sum",
) -> pd.DataFrame:
    """Mean score across all maps played.
    
    Missing scores are counted as 0 for individual players.
    Note: aggregate parameter is ignored for avg_score (always computes mean).
    """
    df = _prep(scores, include)
    if df is None:
        return _empty("avg_score")

    df = _fill_missing_scores(df)
    
    out = (df.groupby("user_id")
             .agg(username=("username", "last"),
                  maps_played=("beatmap_id", "nunique"),
                  avg_score=("score", "mean"))
             .reset_index()
             .sort_values("avg_score", ascending=False)
             .reset_index(drop=True))
    return out[_BASE_COLUMNS + ["avg_score"]]


# ── Average Sum of Placements ─────────────────────────────────────────────────

def avg_placements_leaderboard(
    scores: pd.DataFrame,
    *,
    include: ScorePredicate = include_all,
    aggregate: str = "sum",
) -> pd.DataFrame:
    """Sum of per-map ranks (1 = best). Lower is better.
    
    Missing scores are excluded from calculation (not counted as 0).
    """
    df = _prep(scores, include)
    if df is None:
        return _empty("placement_sum")

    # rank within each map: highest score = rank 1
    df["placement_sum"] = df.groupby("beatmap_id")["score"].rank(
        ascending=False, method="min"
    )
    return _finish(df, "username", "placement_sum", ascending=True, aggregate=aggregate)


# ── Percentile ────────────────────────────────────────────────────────────────

def percentile_leaderboard(
    scores: pd.DataFrame,
    *,
    include: ScorePredicate = include_all,
    aggregate: str = "sum",
) -> pd.DataFrame:
    """Per-map percentiles derived from Z-scores via normal CDF, then aggregated.
    
    Missing scores are excluded from calculation (not counted as 0).
    Formula: convert each Z-score to percentile, then sum or average.
    Returns values between 0 and 1.
    """
    df = _prep(scores, include)
    if df is None:
        return _empty("percentile_sum")

    import math
    
    # Calculate Z-score per map, then convert each to percentile
    map_stats = df.groupby("beatmap_id")["score"].agg(["mean", "std"])
    df = df.join(map_stats, on="beatmap_id")
    df["z_score"] = ((df["score"] - df["mean"]) / df["std"]).fillna(0.0)
    
    # Convert each Z-score to percentile via normal CDF
    df["percentile_sum"] = df["z_score"].apply(lambda z: 0.5 * (1.0 + math.erf(z / math.sqrt(2))))
    
    return _finish(df, "username", "percentile_sum", ascending=False, aggregate=aggregate)


# ── Zipf's Law ────────────────────────────────────────────────────────────────

def zipf_leaderboard(
    scores: pd.DataFrame,
    *,
    include: ScorePredicate = include_all,
    correction_factor: float = 1.4,
    aggregate: str = "sum",
) -> pd.DataFrame:
    """Sum of 1/(rank + correction) weights per map. Higher is better.
    
    correction = correction_factor * num_maps_in_pool
    Missing scores are excluded from calculation (not counted as 0).
    """
    df = _prep(scores, include)
    if df is None:
        return _empty("zipf_sum")

    num_maps = df["beatmap_id"].nunique()
    correction = correction_factor * num_maps
    
    ranks = df.groupby("beatmap_id")["score"].rank(ascending=False, method="min")
    df["zipf_sum"] = 100.0 / (ranks + correction)
    return _finish(df, "username", "zipf_sum", ascending=False, aggregate=aggregate)


# ── Percent Difference ────────────────────────────────────────────────────────

def pct_diff_leaderboard(
    scores: pd.DataFrame,
    *,
    include: ScorePredicate = include_all,
    aggregate: str = "sum",
) -> pd.DataFrame:
    """Sum of (score - min) / (max - min) per map. Higher is better.
    
    Missing scores are excluded from calculation (not counted as 0).
    Assigns lowest score 0, highest score 1, others linearly in between.
    """
    df = _prep(scores, include)
    if df is None:
        return _empty("pct_diff_sum")

    # Calculate min and max per map
    map_stats = df.groupby("beatmap_id")["score"].agg(["min", "max"])
    df = df.join(map_stats, on="beatmap_id")
    
    # (score - min) / (max - min), handle case where min == max
    df["pct_diff_sum"] = ((df["score"] - df["min"]) / (df["max"] - df["min"])).fillna(0.5) * 100
    
    return _finish(df, "username", "pct_diff_sum", ascending=False, aggregate=aggregate)
