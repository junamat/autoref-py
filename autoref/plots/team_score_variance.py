from __future__ import annotations

import numpy as np
import pandas as pd

from ._style import Format, _encode, _new_fig, _palette, _style


def team_score_variance(
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

    per_match = data.pivot_table(index=["match_id", "beatmap_id"],
                                 columns="team_index", values="total_score")
    if per_match.shape[1] < 2:
        ax.text(0.5, 0.5, "need ≥2 teams", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    per_match["mean"] = per_match.mean(axis=1)
    per_match["std"] = per_match.std(axis=1)
    per_match["cv"] = np.where(per_match["mean"] > 0,
                               per_match["std"] / per_match["mean"] * 100, 0)

    match_std: dict[int, dict[int, float]] = {}
    for (mid, _), row in per_match.iterrows():
        scores = {int(c): row[c] for c in per_match.columns if isinstance(c, int)}
        if len(scores) >= 2:
            mean = np.mean(list(scores.values()))
            for team_idx, score in scores.items():
                match_std.setdefault(mid, {})[team_idx] = score - mean

    team_stds: dict[int, list[float]] = {}
    for _mid, team_devs in match_std.items():
        vals = list(team_devs.values())
        if vals:
            overall_std = np.std(vals) if len(vals) > 1 else 1
            for team_idx, dev in team_devs.items():
                z = float(dev / overall_std) if overall_std > 0 else 0.0
                team_stds.setdefault(team_idx, []).append(z)

    if not team_stds:
        ax.text(0.5, 0.5, "no standardized data", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    teams = sorted(team_stds.keys())
    means = [np.mean(team_stds[t]) for t in teams]
    stds = [np.std(team_stds[t]) for t in teams]

    x = np.arange(len(teams))
    colors = [p["green"] if m >= 0 else p["red"] for m in means]
    ax.bar(x, means, yerr=stds, color=colors, alpha=0.7,
           edgecolor=p["border"], linewidth=0.5, capsize=3)

    ax.axhline(0, color=p["muted"], linewidth=0.6, linestyle="--", alpha=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels([f"Team {t}" for t in teams], fontsize=8)
    ax.set_ylabel("standardized score deviation")
    ax.set_title("team score variance · streaky vs steady")
    return _encode(fig, fmt)
