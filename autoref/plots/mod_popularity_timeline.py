from __future__ import annotations

import numpy as np
import pandas as pd

from ._style import Format, _encode, _new_fig, _palette, _style


def mod_popularity_timeline(
    data: pd.DataFrame,
    *,
    fmt: Format = "png",
    theme: str = "dark",
    mod_group_by_bid: dict[int, str] | None = None,
) -> bytes:
    p = _palette(theme)
    fig = _new_fig(fmt)
    ax = fig.add_subplot(111)
    _style(fig, ax, p)

    if data.empty:
        ax.text(0.5, 0.5, "no pick data", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    df = data.copy()
    mod_group_by_bid = mod_group_by_bid or {}
    df["mod_group"] = df["beatmap_id"].map(
        lambda b: mod_group_by_bid.get(int(b), "NM"))

    if "round_name" not in df.columns or df["round_name"].isna().all():
        ax.text(0.5, 0.5, "no round data", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    cross = pd.crosstab(df["round_name"], df["mod_group"])
    cross = cross.sort_index()
    pct = cross.div(cross.sum(axis=1), axis=0) * 100

    if pct.empty:
        ax.text(0.5, 0.5, "no timeline data", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    x = np.arange(len(pct))
    colors = [p["blue"], p["green"], p["yellow"], p["red"],
              p["muted"], "#a78bfa", "#f472b6", "#34d399"]
    bottom = np.zeros(len(pct))

    for i, col in enumerate(pct.columns):
        vals = pct[col].values
        ax.bar(x, vals, bottom=bottom, label=col,
               color=colors[i % len(colors)], alpha=0.7,
               edgecolor=p["border"], linewidth=0.3)
        bottom += vals

    ax.set_xticks(x)
    ax.set_xticklabels(pct.index, fontsize=7, rotation=45, ha="right")
    ax.set_ylabel("pick share (%)")
    ax.set_title("mod popularity timeline · meta evolution")
    ax.set_ylim(0, 100)
    ax.legend(facecolor=p["panel"], edgecolor=p["border"],
              labelcolor=p["text"], framealpha=0.9, fontsize=7)
    return _encode(fig, fmt)
