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
    "zscore":      ("Z-Sum",                    False),
    "avg_score":   ("Average Score",            False),
    "placements":  ("Avg Sum of Placements",    True),
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
) -> pd.DataFrame:
    """Unified dispatcher. Returns _BASE_COLUMNS + [metric_col] sorted appropriately."""
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
    return fn(scores, include=include)


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


def _empty(metric_col: str) -> pd.DataFrame:
    return pd.DataFrame(columns=_BASE_COLUMNS + [metric_col])


def _finish(df: pd.DataFrame, group_col: str, metric_col: str, ascending: bool) -> pd.DataFrame:
    out = (df.groupby("user_id")
             .agg(username=(group_col, "last"),
                  maps_played=("beatmap_id", "nunique"),
                  **{metric_col: (metric_col, "sum")})
             .reset_index()
             .sort_values(metric_col, ascending=ascending)
             .reset_index(drop=True))
    return out[_BASE_COLUMNS + [metric_col]]


# ── Z-Sum ─────────────────────────────────────────────────────────────────────

def z_sum_leaderboard(
    scores: pd.DataFrame,
    *,
    include: ScorePredicate = include_all,
) -> pd.DataFrame:
    """Per-player Z-Sum. Z = (score − map_mean) / map_std; std=0 → Z=0."""
    df = _prep(scores, include)
    if df is None:
        return _empty("z_sum")

    map_stats = df.groupby("beatmap_id")["score"].agg(["mean", "std"])
    df = df.join(map_stats, on="beatmap_id")
    df["z_sum"] = ((df["score"] - df["mean"]) / df["std"]).fillna(0.0)
    return _finish(df, "username", "z_sum", ascending=False)


# ── Average Score ─────────────────────────────────────────────────────────────

def avg_score_leaderboard(
    scores: pd.DataFrame,
    *,
    include: ScorePredicate = include_all,
) -> pd.DataFrame:
    """Mean score across all maps played."""
    df = _prep(scores, include)
    if df is None:
        return _empty("avg_score")

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
) -> pd.DataFrame:
    """Sum of per-map ranks (1 = best). Lower is better."""
    df = _prep(scores, include)
    if df is None:
        return _empty("placement_sum")

    # rank within each map: highest score = rank 1
    df["placement_sum"] = df.groupby("beatmap_id")["score"].rank(
        ascending=False, method="min"
    )
    return _finish(df, "username", "placement_sum", ascending=True)


# ── Percentile ────────────────────────────────────────────────────────────────

def percentile_leaderboard(
    scores: pd.DataFrame,
    *,
    include: ScorePredicate = include_all,
) -> pd.DataFrame:
    """Sum of per-map percentile ranks (0–100). Higher is better."""
    df = _prep(scores, include)
    if df is None:
        return _empty("percentile_sum")

    df["percentile_sum"] = df.groupby("beatmap_id")["score"].rank(pct=True) * 100
    return _finish(df, "username", "percentile_sum", ascending=False)


# ── Zipf's Law ────────────────────────────────────────────────────────────────

def zipf_leaderboard(
    scores: pd.DataFrame,
    *,
    include: ScorePredicate = include_all,
) -> pd.DataFrame:
    """Sum of 1/rank weights per map. Higher is better."""
    df = _prep(scores, include)
    if df is None:
        return _empty("zipf_sum")

    ranks = df.groupby("beatmap_id")["score"].rank(ascending=False, method="min")
    df["zipf_sum"] = 1.0 / ranks
    return _finish(df, "username", "zipf_sum", ascending=False)


# ── Percent Difference ────────────────────────────────────────────────────────

def pct_diff_leaderboard(
    scores: pd.DataFrame,
    *,
    include: ScorePredicate = include_all,
) -> pd.DataFrame:
    """Sum of (score − map_mean) / map_mean × 100. Higher is better."""
    df = _prep(scores, include)
    if df is None:
        return _empty("pct_diff_sum")

    map_means = df.groupby("beatmap_id")["score"].mean().rename("map_mean")
    df = df.join(map_means, on="beatmap_id")
    df["pct_diff_sum"] = ((df["score"] - df["map_mean"]) / df["map_mean"] * 100).fillna(0.0)
    return _finish(df, "username", "pct_diff_sum", ascending=False)
