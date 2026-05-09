from __future__ import annotations

import pandas as pd

from .._shared import _empty, _finish, _prep
from ..predicates import ScorePredicate, include_all


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

    map_stats = df.groupby("beatmap_id")["score"].agg(["mean", "std"])
    df = df.join(map_stats, on="beatmap_id")
    df["z_score"] = ((df["score"] - df["mean"]) / df["std"]).fillna(0.0)
    df["percentile_sum"] = df["z_score"].apply(lambda z: 0.5 * (1.0 + math.erf(z / math.sqrt(2))))

    return _finish(df, "username", "percentile_sum", ascending=False, aggregate=aggregate)
