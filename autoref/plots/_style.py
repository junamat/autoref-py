from __future__ import annotations

import io
from typing import Literal

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

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
