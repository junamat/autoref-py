from __future__ import annotations

import numpy as np
import pandas as pd

from ._style import Format, _encode, _new_fig, _palette, _style


def score_lead_trajectory(
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

    pivot = data.pivot_table(index=["match_id", "turn"],
                             columns="team_index", values="total_score")
    if pivot.shape[1] < 2:
        ax.text(0.5, 0.5, "need ≥2 teams", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    pivot["lead"] = pivot[0] - pivot[1]

    all_leads: dict[int, list[float]] = {}
    for (_mid, turn), lead in pivot["lead"].items():
        all_leads.setdefault(turn, []).append(lead)

    if not all_leads:
        ax.text(0.5, 0.5, "no trajectory data", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    turns = sorted(all_leads.keys())
    medians = [np.median(all_leads[t]) for t in turns]
    p25 = [np.percentile(all_leads[t], 25) for t in turns]
    p75 = [np.percentile(all_leads[t], 75) for t in turns]

    ax.fill_between(turns, p25, p75, color=p["blue"], alpha=0.15, label="p25–p75")
    ax.plot(turns, medians, color=p["blue"], linewidth=1.5, label="median")
    ax.axhline(0, color=p["muted"], linewidth=0.6, linestyle="--", alpha=0.5)

    ax.set_xlabel("turn")
    ax.set_ylabel("team 0 lead (team0 − team1)")
    ax.set_title("score lead trajectory · drama envelope")
    ax.legend(facecolor=p["panel"], edgecolor=p["border"], labelcolor=p["text"], framealpha=0.9)
    ax.ticklabel_format(axis="y", style="plain")
    return _encode(fig, fmt)
