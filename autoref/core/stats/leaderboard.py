"""Unified sync/async dispatchers for the leaderboard methods."""
from __future__ import annotations

import pandas as pd

from .methods import (
    METHODS,
    PP_METHODS,
    avg_placements_leaderboard,
    avg_score_leaderboard,
    beta_distribution_leaderboard,
    match_cost_bathbot_leaderboard,
    match_cost_flashlight_leaderboard,
    pct_diff_leaderboard,
    percentile_leaderboard,
    pp_leaderboard,
    z_pp_leaderboard,
    z_sum_leaderboard,
    zipf_leaderboard,
)
from .predicates import ScorePredicate, include_all


_SYNC_DISPATCH = {
    "zscore":        z_sum_leaderboard,
    "avg_score":     avg_score_leaderboard,
    "placements":    avg_placements_leaderboard,
    "percentile":    percentile_leaderboard,
    "zipf":          zipf_leaderboard,
    "pct_diff":      pct_diff_leaderboard,
    "mc_flashlight": match_cost_flashlight_leaderboard,
    "mc_bathbot":    match_cost_bathbot_leaderboard,
    "beta_dist":     beta_distribution_leaderboard,
}


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
    if method in PP_METHODS:
        raise ValueError(f"method {method!r} requires async; use leaderboard_async()")
    return _SYNC_DISPATCH[method](scores, include=include, aggregate=aggregate)


async def leaderboard_async(
    scores: pd.DataFrame,
    *,
    method: str = "zscore",
    include: ScorePredicate = include_all,
    aggregate: str = "sum",
    db=None,
) -> pd.DataFrame:
    """Async dispatcher. Handles pp/z_pp methods; delegates others to sync path."""
    if method == "pp":
        return await pp_leaderboard(scores, include=include, aggregate=aggregate, db=db)
    if method == "z_pp":
        return await z_pp_leaderboard(scores, include=include, aggregate=aggregate, db=db)
    return leaderboard(scores, method=method, include=include, aggregate=aggregate)
