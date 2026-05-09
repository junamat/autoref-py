from __future__ import annotations

import pandas as pd

from .._shared import _empty, _finish, _prep
from ..predicates import ScorePredicate, include_all


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
