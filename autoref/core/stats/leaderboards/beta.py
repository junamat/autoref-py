from __future__ import annotations

import pandas as pd

from .._shared import _empty, _finish, _prep
from ..predicates import ScorePredicate, include_all


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
