from __future__ import annotations

import numpy as np
import pandas as pd

from ._style import Format, _encode, _new_fig, _palette, _style


def score_inflation_curve(
    data: pd.DataFrame,
    *,
    fmt: Format = "png",
    theme: str = "dark",
) -> bytes:
    p = _palette(theme)
    fig = _new_fig(fmt)
    ax = fig.add_subplot(111)
    _style(fig, ax, p)

    if data.empty:
        ax.text(0.5, 0.5, "no score data", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    df = data.copy()
    if "round_name" not in df.columns or df["round_name"].isna().all():
        ax.text(0.5, 0.5, "no round data", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    if "passed" in df.columns:
        df = df[df["passed"] == 1]

    by_round = df.groupby("round_name")["score"].agg(["mean", "std", "count"]).reset_index()
    by_round = by_round.sort_values("round_name")

    if by_round.empty:
        ax.text(0.5, 0.5, "no round scores", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    x = np.arange(len(by_round))
    means = by_round["mean"].values
    stds = by_round["std"].fillna(0).values

    ax.plot(x, means, color=p["blue"], linewidth=1.5, marker="o", markersize=4)
    ax.fill_between(x, means - stds, means + stds, color=p["blue"], alpha=0.15)

    ax.set_xticks(x)
    ax.set_xticklabels(by_round["round_name"], fontsize=7, rotation=45, ha="right")
    ax.set_ylabel("mean score")
    ax.set_title("score inflation curve · meta progression")
    ax.ticklabel_format(axis="y", style="plain")
    return _encode(fig, fmt)
