from __future__ import annotations

import numpy as np
import pandas as pd

from ._style import Format, _encode, _new_fig, _palette, _style


def team_strategy_profile(
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
        ax.text(0.5, 0.5, "no action data", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    df = data.copy()
    mod_group_by_bid = mod_group_by_bid or {}
    df["mod_group"] = df["beatmap_id"].map(
        lambda b: mod_group_by_bid.get(int(b), "NM"))
    df["step"] = df["step"].str.upper()

    grouped = df.groupby(["team_index", "step", "mod_group"]).size().reset_index(name="count")
    if grouped.empty:
        ax.text(0.5, 0.5, "no grouped data", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    teams = sorted(grouped["team_index"].unique())
    steps = sorted(grouped["step"].unique())
    mod_groups = sorted(grouped["mod_group"].unique())

    n_teams = len(teams)
    n_steps = len(steps)
    n_mods = len(mod_groups)
    if n_teams == 0 or n_steps == 0 or n_mods == 0:
        ax.text(0.5, 0.5, "insufficient data", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    x = np.arange(n_mods)
    width = 0.8 / (n_teams * n_steps) if (n_teams * n_steps) > 0 else 0.8
    colors_step = {"PICK": p["blue"], "BAN": p["red"], "PROTECT": p["yellow"]}

    idx = 0
    for team in teams:
        for step in steps:
            sub = grouped[(grouped["team_index"] == team) & (grouped["step"] == step)]
            vals = []
            for mg in mod_groups:
                count = sub[sub["mod_group"] == mg]["count"].sum()
                vals.append(count)
            offset = idx * width
            ax.bar(x + offset, vals, width,
                   label=f"T{team} {step}",
                   color=colors_step.get(step, p["muted"]),
                   alpha=0.5 + 0.3 * (team / max(n_teams - 1, 1)),
                   edgecolor=p["border"], linewidth=0.3)
            idx += 1

    ax.set_xticks(x + width * idx / 2)
    ax.set_xticklabels(mod_groups)
    ax.set_ylabel("action count")
    ax.set_title("team strategy profile · actions by mod bracket")
    if idx <= 12:
        ax.legend(facecolor=p["panel"], edgecolor=p["border"],
                  labelcolor=p["text"], framealpha=0.9, fontsize=6)
    return _encode(fig, fmt)
