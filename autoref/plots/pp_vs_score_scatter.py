from __future__ import annotations

import json

import pandas as pd

from ._style import Format, _encode, _new_fig, _palette, _style


def pp_vs_score_scatter(
    scores: pd.DataFrame,
    *,
    fmt: Format = "png",
    theme: str = "dark",
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
    if "pp" not in df.columns:
        ax.text(0.5, 0.5, "pp data not available", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    df = df.dropna(subset=["pp"])
    if df.empty:
        ax.text(0.5, 0.5, "no pp data populated", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    def _parse_mods(val):
        if isinstance(val, str):
            try:
                return tuple(sorted(json.loads(val)))
            except (json.JSONDecodeError, TypeError):
                return ("?",)
        return ("?",)

    df["mod_key"] = df["mods"].apply(_parse_mods)
    mod_keys = df["mod_key"].unique()
    colors = [p["blue"], p["green"], p["yellow"], p["red"],
              p["muted"], "#a78bfa", "#f472b6", "#34d399"]

    for i, mk in enumerate(sorted(mod_keys)):
        sub = df[df["mod_key"] == mk]
        label = "+".join(mk) if mk != ("?",) else "?"
        ax.scatter(sub["score"], sub["pp"], s=12, alpha=0.5,
                   color=colors[i % len(colors)], edgecolor=p["border"],
                   linewidth=0.3, label=label)

    ax.set_xlabel("score")
    ax.set_ylabel("pp")
    ax.set_title("pp vs score · mod sanity check")
    ax.ticklabel_format(axis="x", style="plain")
    ax.legend(facecolor=p["panel"], edgecolor=p["border"],
              labelcolor=p["text"], framealpha=0.9, fontsize=7, markerscale=2)
    return _encode(fig, fmt)
