from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde

from ._style import Format, _encode, _new_fig, _palette, _style


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

    ax.grid(False)

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

    edges = np.histogram_bin_edges(values, bins="fd" if n >= 8 else "sturges")
    ax.hist(values, bins=edges, color=p["blue"], alpha=0.55,
            edgecolor=p["border"], linewidth=0.6, density=True, label="histogram")

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
