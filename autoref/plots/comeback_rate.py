from __future__ import annotations

import numpy as np
import pandas as pd

from ._style import Format, _encode, _new_fig, _palette, _style


def comeback_rate(
    data: pd.DataFrame,
    *,
    fmt: Format = "png",
    theme: str = "dark",
    matches: pd.DataFrame | None = None,
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

    pivot = data.pivot_table(index=["match_id", "turn"],
                             columns="team_index", values="total_score")
    if pivot.shape[1] < 2:
        ax.text(0.5, 0.5, "need ≥2 teams", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    pivot["lead"] = pivot[0] - pivot[1]

    if matches is not None and not matches.empty and "best_of" in matches.columns:
        bo_map = matches.set_index("match_id")["best_of"].to_dict()
    else:
        bo_map = {}

    results: dict[str, list[bool]] = {}
    for match_id, group in pivot.groupby("match_id"):
        turns = sorted(group.index.get_level_values("turn").unique())
        if len(turns) < 2:
            continue
        mid = len(turns) // 2
        mid_turn = turns[mid - 1]
        mid_lead = group.loc[(match_id, mid_turn), "lead"] if (match_id, mid_turn) in group.index else 0
        final_lead = group.loc[(match_id, turns[-1]), "lead"] if (match_id, turns[-1]) in group.index else 0

        if mid_lead == 0 or final_lead == 0:
            continue

        trailing_came_back = (mid_lead > 0 and final_lead < 0) or (mid_lead < 0 and final_lead > 0)
        bo = bo_map.get(match_id, 0)
        key = f"Bo{bo}" if bo else "all"
        results.setdefault(key, []).append(trailing_came_back)

    if not results:
        ax.text(0.5, 0.5, "not enough matches", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    keys = sorted(results.keys())
    rates = [sum(results[k]) / len(results[k]) * 100 for k in keys]
    counts = [len(results[k]) for k in keys]

    x = np.arange(len(keys))
    ax.bar(x, rates, color=p["green"], alpha=0.7, edgecolor=p["border"], linewidth=0.5)

    for i, (rate, count) in enumerate(zip(rates, counts)):
        ax.text(i, rate + 1, f"{rate:.0f}%\n(n={count})", ha="center",
                fontsize=7, color=p["text"])

    ax.set_xticks(x)
    ax.set_xticklabels(keys)
    ax.set_ylabel("comeback rate (%)")
    ax.set_title("comeback rate · trailing at half → wins")
    ax.set_ylim(0, max(rates) * 1.25 + 5 if rates else 100)
    return _encode(fig, fmt)
