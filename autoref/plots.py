"""Stat plots for the web UI.

Soft dependency: requires matplotlib + scipy (install via the [plots] extra).
Each renderer takes a DataFrame and returns the encoded image as bytes.
The web layer translates query params to the right DataFrame and picks a format.

Output formats are chosen by the caller:
    fmt="png"   — display PNG (144 dpi, ~800px wide)
    fmt="hires" — high-DPI PNG download (300 dpi, ~1800px wide)
    fmt="svg"   — vector SVG download

Door left open for an interactive future: each function returns a Figure
internally and only encodes at the end. Swapping in a Plotly backend later
means rewriting these functions to return JSON, not rerouting the API.
"""
from __future__ import annotations

import io
from typing import Literal

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde


Format = Literal["png", "hires", "svg"]

_DPI = {"png": 144, "hires": 300, "svg": 96}
_FIGSIZE = {"png": (8, 4.5), "hires": (10, 6), "svg": (8, 4.5)}


def _new_fig(fmt: Format):
    fig = plt.figure(figsize=_FIGSIZE[fmt], dpi=_DPI[fmt])
    return fig


def _encode(fig, fmt: Format) -> bytes:
    buf = io.BytesIO()
    if fmt == "svg":
        fig.savefig(buf, format="svg", bbox_inches="tight")
    else:
        fig.savefig(buf, format="png", dpi=_DPI[fmt], bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def _palette(theme: str = "dark") -> dict:
    """Pull from the same hex values as autoref/web/static/style.css.

    Updating CSS without updating this dict drifts the visuals — it's a small
    enough surface that duplication beats parsing the stylesheet at runtime.
    """
    if theme == "light":
        return {
            "bg":     "#ffffff",
            "panel":  "#ffffff",
            "border": "#d1ccc3",
            "muted":  "#9ca3af",
            "text":   "#1f2937",
            "blue":   "#1d4ed8",
            "green":  "#15803d",
            "yellow": "#b45309",
            "red":    "#dc2626",
        }
    return {
        "bg":     "#1f2937",
        "panel":  "#1f2937",
        "border": "#374151",
        "muted":  "#6b7280",
        "text":   "#d1d5db",
        "blue":   "#60a5fa",
        "green":  "#34d399",
        "yellow": "#fbbf24",
        "red":    "#f87171",
    }


def _style(fig, ax, p: dict) -> None:
    fig.patch.set_facecolor(p["panel"])
    ax.set_facecolor(p["panel"])
    for spine in ax.spines.values():
        spine.set_color(p["border"])
    ax.tick_params(colors=p["muted"], which="both")
    ax.xaxis.label.set_color(p["text"])
    ax.yaxis.label.set_color(p["text"])
    ax.title.set_color(p["text"])
    ax.grid(True, color=p["border"], linewidth=0.5, alpha=0.6)


# ── plot 1: score distribution per map (KDE + histogram) ─────────────────────

def score_distribution(
    scores: pd.DataFrame,
    beatmap_id: int,
    *,
    fmt: Format = "png",
    theme: str = "dark",
    exclude_failed: bool = True,
    label: str | None = None,
) -> bytes:
    """Histogram + KDE of passing scores on a single map.

    `scores` must include columns: beatmap_id, score, passed.
    `label` is shown in the title in place of the raw beatmap id (e.g. "NM1").
    Returns encoded image bytes.
    """
    map_label = label or f"beatmap {beatmap_id}"
    p = _palette(theme)
    fig = _new_fig(fmt)
    ax = fig.add_subplot(111)
    _style(fig, ax, p)

    df = scores[scores["beatmap_id"] == int(beatmap_id)].copy()
    fails = int((df["passed"] == 0).sum()) if "passed" in df.columns else 0
    if exclude_failed and "passed" in df.columns:
        df = df[df["passed"] == 1]

    if df.empty:
        ax.text(0.5, 0.5, f"no scores for {map_label}",
                ha="center", va="center", color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    values = df["score"].astype(float).to_numpy()
    n = values.size

    # FD bin edges; fall back to sturges for very small n
    edges = np.histogram_bin_edges(values, bins="fd" if n >= 8 else "sturges")
    ax.hist(values, bins=edges, color=p["blue"], alpha=0.55,
            edgecolor=p["border"], linewidth=0.6, density=True, label="histogram")

    # KDE (needs n >= 2 and nonzero variance)
    if n >= 2 and values.std() > 0:
        kde = gaussian_kde(values)
        x = np.linspace(values.min(), values.max(), 200)
        ax.fill_between(x, kde(x), color=p["blue"], alpha=0.18, linewidth=0)
        ax.plot(x, kde(x), color=p["blue"], linewidth=1.5, label="KDE")

    mu = values.mean()
    sigma = values.std()
    ax.axvline(mu, color=p["yellow"], linewidth=1.2, label=f"μ={mu:,.0f}")
    if sigma > 0:
        ax.axvline(mu - sigma, color=p["yellow"], linewidth=0.8, linestyle="--", alpha=0.7)
        ax.axvline(mu + sigma, color=p["yellow"], linewidth=0.8, linestyle="--", alpha=0.7,
                   label=f"σ={sigma:,.0f}")

    ax.set_xlabel("score")
    ax.set_ylabel("density")
    ax.set_title(f"score distribution · {map_label}  (n={n}, fails={fails})")
    ax.legend(facecolor=p["panel"], edgecolor=p["border"], labelcolor=p["text"], framealpha=0.9)
    ax.ticklabel_format(axis="x", style="plain")
    return _encode(fig, fmt)


# ── plot 2: pick / ban / protect heat ────────────────────────────────────────

def pickban_heat(
    map_stats: pd.DataFrame,
    *,
    fmt: Format = "png",
    theme: str = "dark",
    code_by_bid: dict[int, str] | None = None,
) -> bytes:
    """Stacked horizontal bars: picks / bans / protects per map, sorted by total.

    `code_by_bid` maps beatmap_id → tournament code (e.g. {3814680: "NM1"}); when
    present, the y-axis shows codes instead of raw IDs.
    """
    p = _palette(theme)
    fig = _new_fig(fmt)
    ax = fig.add_subplot(111)
    _style(fig, ax, p)

    if map_stats.empty:
        ax.text(0.5, 0.5, "no map action data", ha="center", va="center",
                color=p["muted"], transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return _encode(fig, fmt)

    # Pivot long → wide
    wide = map_stats.pivot_table(index="beatmap_id", columns="step",
                                 values="count", fill_value=0)
    for col in ("PICK", "BAN", "PROTECT"):
        if col not in wide.columns:
            wide[col] = 0
    wide["total"] = wide["PICK"] + wide["BAN"] + wide["PROTECT"]
    wide = wide.sort_values("total", ascending=True)  # bottom→top in barh

    y = np.arange(len(wide))
    picks    = wide["PICK"].to_numpy()
    bans     = wide["BAN"].to_numpy()
    protects = wide["PROTECT"].to_numpy()

    ax.barh(y, picks,    color=p["blue"],   edgecolor=p["border"], linewidth=0.5, label="picks")
    ax.barh(y, bans,     left=picks,        color=p["red"],    edgecolor=p["border"], linewidth=0.5, label="bans")
    ax.barh(y, protects, left=picks + bans, color=p["yellow"], edgecolor=p["border"], linewidth=0.5, label="protects")

    ax.set_yticks(y)
    code_by_bid = code_by_bid or {}
    ax.set_yticklabels(
        [code_by_bid.get(int(b)) or str(int(b)) for b in wide.index],
        fontsize=8,
    )
    ax.set_xlabel("count")
    ax.set_title("map activity · picks / bans / protects")
    ax.legend(facecolor=p["panel"], edgecolor=p["border"], labelcolor=p["text"], framealpha=0.9)
    return _encode(fig, fmt)


# ── plot 3: consistency scatter (mean z vs. stddev z) ────────────────────────

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

    sizes = 30 + 8 * agg["n"].to_numpy()  # bigger dot = more maps played
    ax.scatter(agg["mean_z"], agg["std_z"], s=sizes,
               color=p["blue"], alpha=0.7, edgecolor=p["border"], linewidth=0.6)

    # Quadrant guides at population centroid (0, median std)
    ax.axvline(0, color=p["muted"], linewidth=0.6, linestyle="--", alpha=0.5)
    if len(agg) > 1:
        ax.axhline(agg["std_z"].median(), color=p["muted"], linewidth=0.6,
                   linestyle="--", alpha=0.5)

    # Label top-N performers
    top = agg.nlargest(label_top, "mean_z")
    for _, row in top.iterrows():
        ax.annotate(str(row["username"]),
                    xy=(row["mean_z"], row["std_z"]),
                    xytext=(5, 5), textcoords="offset points",
                    fontsize=8, color=p["text"])

    ax.set_xlabel("mean z-score (skill →)")
    ax.set_ylabel("z-score stddev (← consistent · variable →)")
    ax.set_title("player consistency · skill vs. spread")
    return _encode(fig, fmt)


# ── registry ─────────────────────────────────────────────────────────────────

PLOTS: dict[str, str] = {
    "score_distribution": "Score distribution (per map, KDE)",
    "pickban_heat":       "Pick / ban / protect heat",
    "consistency_scatter": "Player consistency",
}
