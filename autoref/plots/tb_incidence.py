from __future__ import annotations

import numpy as np
import pandas as pd

from ._style import Format, _encode, _new_fig, _palette, _style


def tb_incidence(
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
        ax.text(0.5, 0.5, "no match data", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    df = data.copy()
    df["rate"] = np.where(df["total_matches"] > 0,
                          df["tb_matches"] / df["total_matches"] * 100, 0)
    df = df.sort_values("rate", ascending=True)

    y = np.arange(len(df))
    ax.barh(y, df["rate"], color=p["yellow"], edgecolor=p["border"], linewidth=0.5)

    ax.set_yticks(y)
    ax.set_yticklabels([str(r) for r in df["pool_id"]], fontsize=8)
    ax.set_xlabel("tiebreaker rate (%)")
    ax.set_title("tiebreaker incidence per pool")
    for i, (_, row) in enumerate(df.iterrows()):
        ax.text(row["rate"] + 1, i,
                f"{int(row['tb_matches'])}/{int(row['total_matches'])}",
                va="center", fontsize=7, color=p["muted"])
    return _encode(fig, fmt)
