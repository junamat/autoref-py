from __future__ import annotations

import numpy as np
import pandas as pd

from ._style import Format, _encode, _new_fig, _palette, _style


def team_pool_heatmap(
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

    df = data.dropna(subset=["team_name", "pool_id"])
    if df.empty:
        ax.text(0.5, 0.5, "no team/pool data", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    pivot = df.pivot_table(index="team_name", columns="pool_id",
                           values="total_score", aggfunc="mean")
    if pivot.empty:
        ax.text(0.5, 0.5, "no heatmap data", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    im = ax.imshow(pivot.values, cmap="RdYlGn", aspect="auto")

    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, fontsize=8, rotation=45, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)

    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            if not np.isnan(val):
                ax.text(j, i, f"{val:,.0f}", ha="center", va="center",
                        fontsize=6, color=p["text"])

    fig.colorbar(im, ax=ax, shrink=0.8, label="mean score")
    ax.set_title("team × pool heatmap · strength matrix")
    return _encode(fig, fmt)
