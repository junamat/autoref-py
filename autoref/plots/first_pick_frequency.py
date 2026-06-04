from __future__ import annotations

import numpy as np
import pandas as pd

from ._style import Format, _encode, _new_fig, _palette, _style


def first_pick_frequency(
    data: pd.DataFrame,
    *,
    fmt: Format = "png",
    theme: str = "dark",
    code_by_bid: dict[int, str] | None = None,
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

    counts = data["beatmap_id"].value_counts().sort_values(ascending=True)

    code_by_bid = code_by_bid or {}
    labels = [code_by_bid.get(int(b), str(int(b))) for b in counts.index]

    y = np.arange(len(counts))
    ax.barh(y, counts.values, color=p["blue"], edgecolor=p["border"], linewidth=0.5)

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("times picked first")
    ax.set_title("first-pick frequency · opener maps")
    return _encode(fig, fmt)
