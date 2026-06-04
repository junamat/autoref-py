from __future__ import annotations

import numpy as np
import pandas as pd

from ._style import Format, _encode, _new_fig, _palette, _style


def pick_and_win_rate(
    data: pd.DataFrame,
    *,
    fmt: Format = "png",
    theme: str = "dark",
    code_by_bid: dict[int, str] | None = None,
    min_picks: int = 5,
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

    df = data[data["picks"] >= min_picks].copy()
    if df.empty:
        ax.text(0.5, 0.5, f"no maps with ≥{min_picks} picks",
                ha="center", va="center", color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    df["win_rate"] = np.where(df["picks"] > 0, df["wins"] / df["picks"] * 100, 0)
    df = df.sort_values("win_rate", ascending=True)

    code_by_bid = code_by_bid or {}
    labels = [code_by_bid.get(int(b), str(int(b))) for b in df["beatmap_id"]]

    y = np.arange(len(df))
    colors = [p["green"] if wr >= 50 else p["red"] for wr in df["win_rate"]]
    ax.barh(y, df["win_rate"], color=colors, edgecolor=p["border"], linewidth=0.5)

    ax.axvline(50, color=p["muted"], linewidth=0.6, linestyle="--", alpha=0.5)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("picker win rate (%)")
    ax.set_title(f"pick & win rate (min {min_picks} picks)")
    return _encode(fig, fmt)
