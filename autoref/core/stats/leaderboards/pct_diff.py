from __future__ import annotations

import pandas as pd

from .._shared import _empty, _finish, _prep
from ..predicates import ScorePredicate, include_all


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

    map_stats = df.groupby("beatmap_id")["score"].agg(["min", "max"])
    df = df.join(map_stats, on="beatmap_id")
    df["pct_diff_sum"] = ((df["score"] - df["min"]) / (df["max"] - df["min"])).fillna(0.5) * 100

    return _finish(df, "username", "pct_diff_sum", ascending=False, aggregate=aggregate)
