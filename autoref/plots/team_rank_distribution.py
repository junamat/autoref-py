from __future__ import annotations

import numpy as np
import pandas as pd

from ._style import Format, _encode, _new_fig, _palette, _style


def team_rank_distribution(
    scores: pd.DataFrame,
    *,
    fmt: Format = "png",
    theme: str = "dark",
    exclude_failed: bool = True,
) -> bytes:
    p = _palette(theme)
    fig = _new_fig(fmt)
    ax = fig.add_subplot(111)
    _style(fig, ax, p)

    if scores.empty:
        ax.text(0.5, 0.5, "no score data", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    df = scores.copy()
    if exclude_failed and "passed" in df.columns:
        df = df[df["passed"] == 1]
    if df.empty:
        ax.text(0.5, 0.5, "no passing scores", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    df = df.sort_values("score", ascending=False)
    df["intra_rank"] = df.groupby(["match_id", "beatmap_id", "team_index"]).cumcount() + 1

    max_rank = int(df["intra_rank"].max())
    if max_rank < 1:
        ax.text(0.5, 0.5, "no rank data", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    player_ranks = df.groupby(["user_id", "username", "intra_rank"]).size().reset_index(name="count")
    player_totals = df.groupby(["user_id", "username"]).size().reset_index(name="total")
    player_ranks = player_ranks.merge(player_totals, on=["user_id", "username"])
    player_ranks["pct"] = player_ranks["count"] / player_ranks["total"] * 100

    top_players = player_totals.nlargest(15, "total")["user_id"]
    player_ranks = player_ranks[player_ranks["user_id"].isin(top_players)]

    pivot = player_ranks.pivot_table(index="username", columns="intra_rank",
                                     values="pct", fill_value=0)
    if pivot.empty:
        ax.text(0.5, 0.5, "no rank distribution", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    ranks = sorted(pivot.columns)
    y = np.arange(len(pivot))
    left = np.zeros(len(pivot))
    colors = [p["green"], p["blue"], p["yellow"], p["red"],
              p["muted"], "#a78bfa", "#f472b6", "#34d399"]

    for rank in ranks:
        vals = pivot[rank].values if rank in pivot.columns else np.zeros(len(pivot))
        ax.barh(y, vals, left=left, label=f"#{rank}",
                color=colors[(rank - 1) % len(colors)], alpha=0.7,
                edgecolor=p["border"], linewidth=0.3)
        left += vals

    ax.set_yticks(y)
    ax.set_yticklabels(pivot.index.tolist(), fontsize=8)
    ax.set_xlabel("% of maps at rank")
    ax.set_title("team rank distribution · carry vs support")
    ax.legend(facecolor=p["panel"], edgecolor=p["border"],
              labelcolor=p["text"], framealpha=0.9, fontsize=7, title="rank")
    return _encode(fig, fmt)
