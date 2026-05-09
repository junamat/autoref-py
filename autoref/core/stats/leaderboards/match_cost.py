from __future__ import annotations

import pandas as pd

from .._shared import _BASE_COLUMNS, _empty, _prep
from ..predicates import ScorePredicate, include_all


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


def match_cost_bathbot_leaderboard(
    scores: pd.DataFrame,
    *,
    include: ScorePredicate = include_all,
    aggregate: str = "mean",
) -> pd.DataFrame:
    """Bathbot match cost — computed per `match_id`, aggregated across matches.

    Cost = (Σ(score / avg_score) + 0.5*n' + tb_bonus) / n'
           * 1.4 ^ (((n'-1)/(n-1)) ** 0.6)
           * (1 + 0.02 * max(0, m - 2))
            tb_bonus = (tb_score / avg_tb_score) if player played the tiebreaker map, else 0

    n  — number of maps played in the match
    n' — maps this player participated in
    m  — distinct mod combinations the player used in the match

    TB map identified via `matches.tb_beatmap_id` (snapshotted at match save).
    """
    df = _prep(scores, include)
    if df is None or "match_id" not in df.columns:
        return _empty("mc_bathbot")

    avg_per_game = df.groupby(["match_id", "turn"])["score"].transform("mean")
    df = df.assign(_ratio=df["score"] / avg_per_game.replace(0, pd.NA)).dropna(subset=["_ratio"])

    rows = []
    for _match_id, mdf in df.groupby("match_id"):
        n = mdf["turn"].nunique()
        if n < 1:
            continue
        tb_bid = mdf["tb_beatmap_id"].iloc[0] if "tb_beatmap_id" in mdf.columns else None
        tb_played = tb_bid is not None and pd.notna(tb_bid)
        for user_id, pdf in mdf.groupby("user_id"):
            n_prime = pdf["turn"].nunique()
            if n_prime == 0:
                continue
            ratio_sum = float(pdf["_ratio"].sum())
            tb_bonus: float = 0.0
            if tb_played:
                tb_rows = pdf[pdf["beatmap_id"] == tb_bid]
                if not tb_rows.empty:
                    tb_bonus = float(tb_rows["_ratio"].iloc[0])
            m = pdf["mods"].nunique() if "mods" in pdf.columns else 1
            base = (ratio_sum + 0.5 * n_prime + tb_bonus) / n_prime
            if n > 1:
                participation = 1.4 ** (((n_prime - 1) / (n - 1)) ** 0.6)
            else:
                participation = 1.0
            mod_bonus = 1.0 + 0.02 * max(0, m - 2)
            cost = base * participation * mod_bonus
            rows.append({
                "user_id":    user_id,
                "username":   pdf["username"].iloc[-1],
                "n_prime":    n_prime,
                "mc_bathbot": cost,
            })

    if not rows:
        return _empty("mc_bathbot")

    per_match = pd.DataFrame(rows)
    agg_func = "mean" if aggregate == "mean" else "sum"
    out = (per_match.groupby("user_id")
                    .agg(username=("username", "last"),
                         maps_played=("n_prime", "sum"),
                         mc_bathbot=("mc_bathbot", agg_func))
                    .reset_index()
                    .sort_values("mc_bathbot", ascending=False)
                    .reset_index(drop=True))
    return out[_BASE_COLUMNS + ["mc_bathbot"]]
