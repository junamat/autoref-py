from __future__ import annotations

import numpy as np
import pandas as pd

from ._style import Format, _encode, _new_fig, _palette, _style


def map_close_factor(
    data: pd.DataFrame,
    *,
    fmt: Format = "png",
    theme: str = "dark",
    code_by_bid: dict[int, str] | None = None,
) -> bytes:
    """Map closeness: lower = closer scores.

    Supports two formats:
    - Team matches (match_id, beatmap_id, team_index, total_score): uses |team1 - team2|
    - FFA qualifiers (beatmap_id, score): uses coefficient of variation (std/mean)
    """
    p = _palette(theme)
    fig = _new_fig(fmt)
    ax = fig.add_subplot(111)
    _style(fig, ax, p)

    if data.empty:
        ax.text(0.5, 0.5, "no score data", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    # Detect format: team matches vs FFA
    is_team_format = "match_id" in data.columns and "team_index" in data.columns

    if is_team_format:
        # Team match format: calculate |team1 - team2| per match
        pivot = data.pivot_table(index=["match_id", "beatmap_id"],
                                 columns="team_index", values="total_score")
        if pivot.shape[1] < 2:
            ax.text(0.5, 0.5, "need ≥2 teams per match", ha="center", va="center",
                    color=p["muted"], transform=ax.transAxes)
            ax.set_xticks([]); ax.set_yticks([])
            return _encode(fig, fmt)

        pivot["abs_diff"] = (pivot[0] - pivot[1]).abs()
        diffs = pivot.groupby("beatmap_id")["abs_diff"]
        means = diffs.mean().sort_values(ascending=True)
        stds = diffs.std().fillna(0)
        xlabel = "mean |team1 − team2| score diff"
    else:
        # FFA format: use coefficient of variation (std/mean) per map
        if "score" not in data.columns:
            ax.text(0.5, 0.5, "missing score column", ha="center", va="center",
                    color=p["muted"], transform=ax.transAxes)
            ax.set_xticks([]); ax.set_yticks([])
            return _encode(fig, fmt)

        map_stats = data.groupby("beatmap_id")["score"].agg(["mean", "std", "count"])
        map_stats = map_stats[map_stats["count"] >= 2]  # Need at least 2 scores
        if map_stats.empty:
            ax.text(0.5, 0.5, "need ≥2 scores per map", ha="center", va="center",
                    color=p["muted"], transform=ax.transAxes)
            ax.set_xticks([]); ax.set_yticks([])
            return _encode(fig, fmt)

        # Coefficient of variation (std/mean), normalized to percentage
        map_stats["cv"] = (map_stats["std"] / map_stats["mean"]).fillna(0) * 100
        means = map_stats["cv"].sort_values(ascending=True)
        stds = pd.Series([0.0] * len(means), index=means.index)  # No error bars for CV
        xlabel = "score coefficient of variation (%)"

    code_by_bid = code_by_bid or {}
    labels = [code_by_bid.get(int(b), str(int(b))) for b in means.index]

    y = np.arange(len(means))
    ax.barh(y, means, xerr=stds, color=p["blue"], alpha=0.7,
            edgecolor=p["border"], linewidth=0.5, capsize=2)

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel(xlabel)
    ax.set_title("map closeness · blowout ↔ swing")
    ax.ticklabel_format(axis="x", style="plain")
    return _encode(fig, fmt)
