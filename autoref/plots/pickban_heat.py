from __future__ import annotations

import numpy as np
import pandas as pd

from ._style import Format, _encode, _new_fig, _palette, _style


def pickban_heat(
    map_actions: pd.DataFrame,
    *,
    fmt: Format = "png",
    theme: str = "dark",
    code_by_bid: dict[int, str] | None = None,
) -> bytes:
    """Stacked horizontal bars: bans / picks / protects per map, sorted by total.

    Stacking, left → right:
      1. bans
      2. picks (with a hatched yellow overlay for picks-while-protected)
      3. protects-without-pick

    `map_actions` columns: beatmap_id, bans, picks, picks_while_protected,
    protect_only (see MatchDatabase.get_map_action_breakdown).
    `code_by_bid` maps beatmap_id → tournament code (e.g. {3814680: "NM1"}); when
    present, the y-axis shows codes instead of raw IDs.
    """
    p = _palette(theme)
    fig = _new_fig(fmt)
    ax = fig.add_subplot(111)
    _style(fig, ax, p)

    if map_actions.empty:
        ax.text(0.5, 0.5, "no map action data", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    df = map_actions.copy().set_index("beatmap_id")
    for col in ("bans", "picks", "picks_while_protected", "protect_only"):
        if col not in df.columns:
            df[col] = 0
    df["total"] = df["bans"] + df["picks"] + df["protect_only"]
    df = df.sort_values("total", ascending=True)

    y          = np.arange(len(df))
    bans       = df["bans"].to_numpy()
    picks      = df["picks"].to_numpy()
    pwp        = df["picks_while_protected"].to_numpy()
    prot_only  = df["protect_only"].to_numpy()

    ax.grid(axis="y", visible=False)

    ax.barh(y, bans,      color=p["red"],    edgecolor=p["border"], linewidth=0.5, label="bans")
    ax.barh(y, picks,     left=bans,         color=p["blue"],   edgecolor=p["border"], linewidth=0.5, label="picks")
    ax.barh(y, pwp, left=bans + picks, color=p["yellow"], edgecolor=p["border"],
            linewidth=0.5, hatch="///", alpha=0.85, label="picks while protected")
    ax.barh(y, prot_only, left=bans + picks + pwp, color=p["yellow"], edgecolor=p["border"],
            linewidth=0.5, label="protects (no pick)")

    ax.set_yticks(y)
    code_by_bid = code_by_bid or {}
    ax.set_yticklabels(
        [code_by_bid.get(int(b)) or str(int(b)) for b in df.index],
        fontsize=8,
    )
    ax.set_xlabel("count")
    ax.set_title("map activity · bans / picks / protects")
    ax.legend(facecolor=p["panel"], edgecolor=p["border"], labelcolor=p["text"], framealpha=0.9)
    return _encode(fig, fmt)
