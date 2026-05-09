from __future__ import annotations

import pandas as pd

from .._shared import _empty, _finish, _prep
from ..predicates import ScorePredicate, include_all


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

    df["placement_sum"] = df.groupby("beatmap_id")["score"].rank(
        ascending=False, method="min"
    )
    return _finish(df, "username", "placement_sum", ascending=True, aggregate=aggregate)
