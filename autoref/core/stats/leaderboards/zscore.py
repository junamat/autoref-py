from __future__ import annotations

import pandas as pd

from .._shared import _empty, _finish, _prep
from ..predicates import ScorePredicate, include_all


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
