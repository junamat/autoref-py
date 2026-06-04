from __future__ import annotations

import pandas as pd

from ._style import Format, _encode, _new_fig, _palette, _style


def pp_consistency_scatter(
    scores: pd.DataFrame,
    *,
    fmt: Format = "png",
    theme: str = "dark",
    exclude_failed: bool = True,
    label_top: int = 5,
) -> bytes:
    p = _palette(theme)
    fig = _new_fig(fmt)
    ax = fig.add_subplot(111)
    _style(fig, ax, p)

    df = scores.copy()
    if exclude_failed and "passed" in df.columns:
        df = df[df["passed"] == 1]
    if df.empty:
        ax.text(0.5, 0.5, "no score data", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    has_pp = "pp" in df.columns and df["pp"].notna().any()
    value_col = "pp" if has_pp else "score"
    value_label = "pp" if has_pp else "score"

    df = df.sort_values(value_col, ascending=False).drop_duplicates(
        subset=["user_id", "beatmap_id"])
    map_stats = df.groupby("beatmap_id")[value_col].agg(["mean", "std"])
    df = df.join(map_stats, on="beatmap_id", rsuffix="_map")
    df["z"] = ((df[value_col] - df["mean"]) / df["std"]).fillna(0.0)

    agg = (df.groupby("user_id")
             .agg(username=("username", "last"),
                  mean_z=("z", "mean"),
                  std_z=("z", "std"),
                  n=("beatmap_id", "nunique"))
             .reset_index())
    agg["std_z"] = agg["std_z"].fillna(0.0)

    if agg.empty:
        ax.text(0.5, 0.5, "no aggregate data", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    sizes = 30 + 8 * agg["n"].to_numpy()
    ax.scatter(agg["mean_z"], agg["std_z"], s=sizes,
               color=p["blue"], alpha=0.7, edgecolor=p["border"], linewidth=0.6)

    ax.axvline(0, color=p["muted"], linewidth=0.6, linestyle="--", alpha=0.5)
    if len(agg) > 1:
        ax.axhline(agg["std_z"].median(), color=p["muted"], linewidth=0.6,
                   linestyle="--", alpha=0.5)

    top = agg.nlargest(label_top, "mean_z")
    for _, row in top.iterrows():
        ax.annotate(str(row["username"]),
                    xy=(row["mean_z"], row["std_z"]),
                    xytext=(5, 5), textcoords="offset points",
                    fontsize=8, color=p["text"])

    ax.set_ylim(bottom=0)
    ax.set_xlabel(f"mean z-{value_label}")
    ax.set_ylabel(f"z-{value_label} stddev")
    ax.set_title(f"player consistency · {value_label}-based")
    return _encode(fig, fmt)
