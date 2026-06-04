from __future__ import annotations

from collections import Counter

import pandas as pd

from ._style import Format, _encode, _new_fig, _palette, _style


def action_sankey(
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
    df["mod"] = df["beatmap_id"].map(
        lambda b: mod_group_by_bid.get(int(b), "UNK")
    )
    df["node"] = df["step"].str.upper() + ":" + df["mod"]

    transitions: Counter[tuple[str, str]] = Counter()
    for _, match_df in df.groupby("match_id"):
        nodes = match_df.sort_values("turn")["node"].tolist()
        for i in range(len(nodes) - 1):
            transitions[(nodes[i], nodes[i + 1])] += 1

    if not transitions:
        ax.text(0.5, 0.5, "no transitions found", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    top = transitions.most_common(20)
    max_count = top[0][1] if top else 1

    for (src, dst), count in top:
        src_y = hash(src) % 100 / 100
        dst_y = hash(dst) % 100 / 100
        lw = 0.5 + 4.0 * (count / max_count)
        ax.annotate("", xy=(0.7, dst_y), xytext=(0.3, src_y),
                    arrowprops=dict(arrowstyle="-", color=p["blue"],
                                    lw=lw, alpha=0.4 + 0.4 * count / max_count))
        ax.text(0.5, (src_y + dst_y) / 2, str(count), fontsize=6,
                color=p["muted"], ha="center", va="center")

    seen = set()
    for (src, dst), _ in top:
        if src not in seen:
            ax.text(0.25, hash(src) % 100 / 100, src, fontsize=6,
                    color=p["text"], ha="right", va="center")
            seen.add(src)
        if dst not in seen:
            ax.text(0.75, hash(dst) % 100 / 100, dst, fontsize=6,
                    color=p["text"], ha="left", va="center")
            seen.add(dst)

    ax.set_xlim(0, 1)
    ax.set_ylim(-0.05, 1.05)
    ax.set_title("action flow · top 20 transitions")
    ax.set_xticks([])
    ax.set_yticks([])
    return _encode(fig, fmt)
