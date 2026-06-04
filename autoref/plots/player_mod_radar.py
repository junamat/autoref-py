from __future__ import annotations

import json

import numpy as np
import pandas as pd

from ._style import Format, _encode, _new_fig, _palette, _style


def player_mod_radar(
    scores: pd.DataFrame,
    *,
    fmt: Format = "png",
    theme: str = "dark",
    mod_group_by_bid: dict[int, str] | None = None,
    exclude_failed: bool = True,
    top_n: int = 10,
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

    mod_group_by_bid = mod_group_by_bid or {}

    def _get_mod_group(row):
        # First try actual mods played on this score
        if "mods" in row and pd.notna(row["mods"]):
            try:
                mods = json.loads(row["mods"]) if isinstance(row["mods"], str) else row["mods"]
                if isinstance(mods, list) and mods:
                    filtered = [m.upper() for m in mods if m.upper() != "NF"]
                    if filtered:
                        return "".join(sorted(filtered))
            except Exception:
                pass

        # Fall back to pool structure, but ignore generic group names
        pool_group = mod_group_by_bid.get(int(row["beatmap_id"]))
        if pool_group and pool_group.upper() not in ("MAP", "MISC", ""):
            return pool_group
        return "NM"

    df["mod_group"] = df.apply(_get_mod_group, axis=1)

    df = df.sort_values("score", ascending=False).drop_duplicates(
        subset=["user_id", "beatmap_id"])
    map_stats = df.groupby("beatmap_id")["score"].agg(["mean", "std"])
    df = df.join(map_stats, on="beatmap_id")
    df["z"] = ((df["score"] - df["mean"]) / df["std"]).fillna(0.0)

    player_mod = df.groupby(["user_id", "username", "mod_group"])["z"].mean().reset_index()
    if player_mod.empty:
        ax.text(0.5, 0.5, "no mod data", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    player_avg = df.groupby(["user_id", "username"])["z"].mean().reset_index()
    top_players = player_avg.nlargest(top_n, "z")
    top_ids = set(top_players["user_id"])
    player_mod = player_mod[player_mod["user_id"].isin(top_ids)]

    pivot = player_mod.pivot_table(index="username", columns="mod_group",
                                   values="z", fill_value=0)
    if pivot.empty:
        ax.text(0.5, 0.5, "no mod groups", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    mod_groups = sorted(pivot.columns)
    n_mods = len(mod_groups)
    x = np.arange(n_mods)
    width = 0.8 / len(pivot)
    colors = [p["blue"], p["green"], p["yellow"], p["red"],
              p["muted"], "#a78bfa", "#f472b6", "#34d399",
              "#fb923c", "#38bdf8"]

    for i, (username, row) in enumerate(pivot.iterrows()):
        vals = [row.get(mg, 0) for mg in mod_groups]
        ax.bar(x + i * width, vals, width, label=username,
               color=colors[i % len(colors)], alpha=0.7,
               edgecolor=p["border"], linewidth=0.3)

    ax.set_xticks(x + width * len(pivot) / 2)
    ax.set_xticklabels(mod_groups)
    ax.set_ylabel("mean z-score")
    ax.set_title(f"player mod profile · top {top_n} by mean z")
    ax.axhline(0, color=p["muted"], linewidth=0.5, linestyle="--", alpha=0.5)
    if len(pivot) <= 6:
        ax.legend(facecolor=p["panel"], edgecolor=p["border"],
                  labelcolor=p["text"], framealpha=0.9, fontsize=7)
    return _encode(fig, fmt)
