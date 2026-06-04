from __future__ import annotations

import numpy as np
import pandas as pd

from ._style import Format, _encode, _new_fig, _palette, _style


def upset_rate_by_round(
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
        ax.text(0.5, 0.5, "no seed data", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    df = data.copy()
    if "round_name" not in df.columns:
        ax.text(0.5, 0.5, "no round data", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    if "upset" not in df.columns:
        ax.text(0.5, 0.5, "no upset column", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    by_round = df.groupby("round_name").agg(
        total=("upset", "count"),
        upsets=("upset", "sum"),
    ).reset_index()
    by_round["rate"] = np.where(by_round["total"] > 0,
                                by_round["upsets"] / by_round["total"] * 100, 0)
    by_round = by_round.sort_values("round_name")

    if by_round.empty:
        ax.text(0.5, 0.5, "no round upsets", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    x = np.arange(len(by_round))
    ax.bar(x, by_round["rate"], color=p["red"], alpha=0.7,
           edgecolor=p["border"], linewidth=0.5)

    for i, (_, row) in enumerate(by_round.iterrows()):
        ax.text(i, row["rate"] + 1,
                f"{row['rate']:.0f}%\n({int(row['upsets'])}/{int(row['total'])})",
                ha="center", fontsize=7, color=p["text"])

    ax.set_xticks(x)
    ax.set_xticklabels(by_round["round_name"], fontsize=7, rotation=45, ha="right")
    ax.set_ylabel("upset rate (%)")
    ax.set_title("upset rate by round · lower seed wins")
    ax.set_ylim(0, max(by_round["rate"]) * 1.3 + 5 if len(by_round) else 100)
    return _encode(fig, fmt)
