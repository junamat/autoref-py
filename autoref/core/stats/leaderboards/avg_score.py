from __future__ import annotations

import pandas as pd

from .._shared import _BASE_COLUMNS, _empty, _fill_missing_scores, _prep
from ..predicates import ScorePredicate, include_all


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
