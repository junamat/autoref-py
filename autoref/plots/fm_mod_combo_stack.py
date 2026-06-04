from __future__ import annotations

import json

import numpy as np
import pandas as pd

from ._style import Format, _encode, _new_fig, _palette, _style


def fm_mod_combo_stack(
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
        ax.text(0.5, 0.5, "no score data", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    df = data.copy()
    mod_group_by_bid = mod_group_by_bid or {}
    df["mod_group"] = df["beatmap_id"].map(
        lambda b: mod_group_by_bid.get(int(b), "NM"))

    fm_data = df[df["mod_group"] == "FM"]
    if fm_data.empty:
        ax.text(0.5, 0.5, "no FM data", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    def _parse_mods(val):
        if isinstance(val, str):
            try:
                mods = json.loads(val)
                return "+".join(sorted(mods)) if mods else "NM"
            except (json.JSONDecodeError, TypeError):
                return "?"
        return "?"

    fm_data = fm_data.copy()
    fm_data["mod_combo"] = fm_data["mods"].apply(_parse_mods)

    cross = pd.crosstab(fm_data["beatmap_id"], fm_data["mod_combo"])
    if cross.empty:
        ax.text(0.5, 0.5, "no mod combos", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    labels = [str(b) for b in cross.index]

    x = np.arange(len(cross))
    colors = [p["blue"], p["green"], p["yellow"], p["red"],
              p["muted"], "#a78bfa", "#f472b6", "#34d399"]
    bottom = np.zeros(len(cross))

    for i, col in enumerate(cross.columns):
        vals = cross[col].values
        ax.bar(x, vals, bottom=bottom, label=col,
               color=colors[i % len(colors)], alpha=0.7,
               edgecolor=p["border"], linewidth=0.3)
        bottom += vals

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7, rotation=45, ha="right")
    ax.set_ylabel("player count")
    ax.set_title("FM mod combo stack · choices per slot")
    ax.legend(facecolor=p["panel"], edgecolor=p["border"],
              labelcolor=p["text"], framealpha=0.9, fontsize=7, title="mod combo")
    return _encode(fig, fmt)
