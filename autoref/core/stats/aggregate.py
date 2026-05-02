"""Team-level aggregation: collapse per-player rows to per-team rows."""
from __future__ import annotations

import pandas as pd

from .leaderboard import leaderboard
from .predicates import ScorePredicate, include_all


def aggregate_to_teams(scores: pd.DataFrame, include: ScorePredicate = include_all) -> pd.DataFrame:
    """Collapse per-player scores into per-team-per-map scores.

    Each output row has team_score = sum of player scores on that map for that
    team in that match. Used as the input to team-level metrics: team metrics
    must operate on summed team scores, not on per-player metrics.

    The returned frame mimics the player-level schema so it can be passed back
    through the existing `leaderboard()` machinery: `user_id` and `username`
    are set to the team_name, and `score` is the team's summed score for that
    (match, beatmap).
    """
    if scores is None or scores.empty:
        return scores.iloc[0:0] if scores is not None else pd.DataFrame()
    df = scores.loc[scores.apply(include, axis=1)].copy()
    if df.empty or "team_name" not in df.columns:
        return df.iloc[0:0]
    df = df.dropna(subset=["team_name"])
    if df.empty:
        return df

    grouped = (df.groupby(["match_id", "beatmap_id", "team_name"], as_index=False)
                 .agg(score=("score", "sum"),
                      passed=("passed", "max")))
    grouped["user_id"] = grouped["team_name"]
    grouped["username"] = grouped["team_name"]
    grouped["accuracy"] = 1.0
    grouped["mods"] = "[]"
    return grouped


def team_leaderboard(
    scores: pd.DataFrame,
    *,
    method: str = "zscore",
    include: ScorePredicate = include_all,
    aggregate: str = "sum",
) -> pd.DataFrame:
    """Team-level leaderboard. Sums player scores per (match, beatmap, team)
    first, then runs the chosen metric over the resulting team scores."""
    team_df = aggregate_to_teams(scores, include=include)
    if team_df.empty:
        return leaderboard(team_df, method=method, include=include_all, aggregate=aggregate)
    return leaderboard(team_df, method=method, include=include_all, aggregate=aggregate)
