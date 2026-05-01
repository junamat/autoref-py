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
    "mc_flashlight": ("Match Cost (Flashlight)", False),
    "mc_bathbot":    ("Match Cost (Bathbot)",    False),
    "beta_dist":     ("Beta Distribution",       False),
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
        "zscore":        z_sum_leaderboard,
        "avg_score":     avg_score_leaderboard,
        "placements":    avg_placements_leaderboard,
        "percentile":    percentile_leaderboard,
        "zipf":          zipf_leaderboard,
        "pct_diff":      pct_diff_leaderboard,
        "mc_flashlight": match_cost_flashlight_leaderboard,
        "mc_bathbot":    match_cost_bathbot_leaderboard,
        "beta_dist":     beta_distribution_leaderboard,
    }[method]
    return fn(scores, include=include, aggregate=aggregate)


# ── team-aggregation entry point ─────────────────────────────────────────────

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


# ── Match Cost: Flashlight (D I O's) ──────────────────────────────────────────

def match_cost_flashlight_leaderboard(
    scores: pd.DataFrame,
    *,
    include: ScorePredicate = include_all,
    aggregate: str = "sum",  # ignored; cost is one number per player
) -> pd.DataFrame:
    """Flashlight match cost.

    Cost = mean(score_i / map_median_i) * cbrt(n_player / m_median)

    map_median_i — median score on map i across players who played it
    n_player     — count of distinct maps this player played
    m_median     — median of n_player across all players
    """
    df = _prep(scores, include)
    if df is None:
        return _empty("mc_flashlight")

    map_median = df.groupby("beatmap_id")["score"].transform("median")
    df = df.assign(_ratio=df["score"] / map_median.replace(0, pd.NA)).dropna(subset=["_ratio"])

    per_player = (df.groupby("user_id")
                    .agg(username=("username", "last"),
                         maps_played=("beatmap_id", "nunique"),
                         _avg_ratio=("_ratio", "mean"))
                    .reset_index())

    if per_player.empty:
        return _empty("mc_flashlight")

    m_median = float(per_player["maps_played"].median())
    if m_median <= 0:
        m_median = 1.0
    per_player["mc_flashlight"] = (
        per_player["_avg_ratio"]
        * (per_player["maps_played"].astype(float) / m_median) ** (1.0 / 3.0)
    )

    return (per_player.sort_values("mc_flashlight", ascending=False)
                      .reset_index(drop=True)
                      [_BASE_COLUMNS + ["mc_flashlight"]])


# ── Match Cost: Bathbot ───────────────────────────────────────────────────────

def match_cost_bathbot_leaderboard(
    scores: pd.DataFrame,
    *,
    include: ScorePredicate = include_all,
    aggregate: str = "mean",
) -> pd.DataFrame:
    """Bathbot match cost — computed per `match_id`, aggregated across matches.

    Cost = (Σ(score / avg_score) + 0.5*n') / n'
           * 1.4 ^ (((n'-1)/(n-1)) ** 0.6)
           * (1 + 0.02 * max(0, m - 2))

    n  — number of games in the match
    n' — games this player participated in
    m  — distinct mod combinations the player used in the match

    Tiebreaker bonus is omitted (TB-map identification needs pool metadata).
    """
    df = _prep(scores, include)
    if df is None or "match_id" not in df.columns:
        return _empty("mc_bathbot")

    avg_per_game = df.groupby(["match_id", "turn"])["score"].transform("mean")
    df = df.assign(_ratio=df["score"] / avg_per_game.replace(0, pd.NA)).dropna(subset=["_ratio"])

    rows = []
    for match_id, mdf in df.groupby("match_id"):
        n = mdf["turn"].nunique()
        if n < 1:
            continue
        for user_id, pdf in mdf.groupby("user_id"):
            n_prime = pdf["turn"].nunique()
            if n_prime == 0:
                continue
            ratio_sum = float(pdf["_ratio"].sum())
            m = pdf["mods"].nunique() if "mods" in pdf.columns else 1
            base = (ratio_sum + 0.5 * n_prime) / n_prime
            if n > 1:
                participation = 1.4 ** (((n_prime - 1) / (n - 1)) ** 0.6)
            else:
                participation = 1.0
            mod_bonus = 1.0 + 0.02 * max(0, m - 2)
            cost = base * participation * mod_bonus
            rows.append({
                "user_id": user_id,
                "username": pdf["username"].iloc[-1],
                "beatmap_id": pdf["beatmap_id"].iloc[0],  # placeholder for nunique downstream
                "mc_bathbot": cost,
            })

    if not rows:
        return _empty("mc_bathbot")

    per_match = pd.DataFrame(rows)
    # aggregate across matches per player
    agg_func = "mean" if aggregate == "mean" else "sum"
    out = (per_match.groupby("user_id")
                    .agg(username=("username", "last"),
                         maps_played=("beatmap_id", "count"),  # = matches played
                         mc_bathbot=("mc_bathbot", agg_func))
                    .reset_index()
                    .sort_values("mc_bathbot", ascending=False)
                    .reset_index(drop=True))
    return out[_BASE_COLUMNS + ["mc_bathbot"]]


# ── Beta Distribution ─────────────────────────────────────────────────────────

def beta_distribution_leaderboard(
    scores: pd.DataFrame,
    *,
    include: ScorePredicate = include_all,
    aggregate: str = "sum",
) -> pd.DataFrame:
    """Per-map fit Beta(α,β) on min-max-normalized scores; player metric = Beta CDF.

    Method of moments: with sample mean μ ∈ (0,1) and variance σ² > 0,
        c = μ(1-μ)/σ² - 1
        α = μ * c,  β = (1-μ) * c
    """
    try:
        from scipy.special import betainc
    except ImportError:
        return _empty("beta_dist")

    df = _prep(scores, include)
    if df is None:
        return _empty("beta_dist")

    df = df.copy()
    df["beta_dist"] = 0.0
    for _bid, idx in df.groupby("beatmap_id").groups.items():
        s = df.loc[idx, "score"].astype(float)
        lo, hi = s.min(), s.max()
        if hi <= lo:
            df.loc[idx, "beta_dist"] = 0.5
            continue
        x = ((s - lo) / (hi - lo)).clip(1e-6, 1 - 1e-6)
        mu = float(x.mean())
        var = float(x.var(ddof=0))
        if var <= 0 or mu <= 0 or mu >= 1:
            df.loc[idx, "beta_dist"] = x.values
            continue
        c = mu * (1 - mu) / var - 1
        if c <= 0:
            df.loc[idx, "beta_dist"] = x.values
            continue
        alpha, beta = mu * c, (1 - mu) * c
        df.loc[idx, "beta_dist"] = betainc(alpha, beta, x.values)

    return _finish(df, "username", "beta_dist", ascending=False, aggregate=aggregate)
