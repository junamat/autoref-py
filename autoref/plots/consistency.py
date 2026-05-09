from __future__ import annotations

import pandas as pd

from ._style import Format, _encode, _new_fig, _palette, _style


def consistency_aggregate(
    scores: pd.DataFrame,
    *,
    exclude_failed: bool = True,
) -> pd.DataFrame:
    """Per-player aggregate of map z-scores: mean_z, std_z, n.

    Shared by the matplotlib renderer and the JSON data endpoint so the
    interactive client and the export image stay in sync.
    """
    df = scores.copy()
    if exclude_failed and "passed" in df.columns:
        df = df[df["passed"] == 1]
    if df.empty:
        return pd.DataFrame(columns=["user_id", "username", "mean_z", "std_z", "n"])

    df = (df.sort_values("score", ascending=False)
            .drop_duplicates(subset=["user_id", "beatmap_id"]))
    map_stats = df.groupby("beatmap_id")["score"].agg(["mean", "std"])
    df = df.join(map_stats, on="beatmap_id")
    df["z"] = ((df["score"] - df["mean"]) / df["std"]).fillna(0.0)

    agg = (df.groupby("user_id")
             .agg(username=("username", "last"),
                  mean_z=("z", "mean"),
                  std_z=("z", "std"),
                  n=("beatmap_id", "nunique"))
             .reset_index())
    agg["std_z"] = agg["std_z"].fillna(0.0)
    return agg


def consistency_scatter(
    scores: pd.DataFrame,
    *,
    fmt: Format = "png",
    theme: str = "dark",
    exclude_failed: bool = True,
    label_top: int = 5,
) -> bytes:
    """Per-player mean z vs. stddev z. Labels top-N by mean z."""
    p = _palette(theme)
    fig = _new_fig(fmt)
    ax = fig.add_subplot(111)
    _style(fig, ax, p)

    agg = consistency_aggregate(scores, exclude_failed=exclude_failed)
    if agg.empty:
        ax.text(0.5, 0.5, "no score data", ha="center", va="center",
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
    ax.set_xlabel("mean z-score (skill →)")
    ax.set_ylabel("z-score stddev (← consistent · variable →)")
    ax.set_title("player consistency · skill vs. spread")
    return _encode(fig, fmt)
