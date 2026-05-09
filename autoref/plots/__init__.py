"""Stat plots for the web UI.

Soft dependency: requires matplotlib + scipy (install via the [plots] extra).
Each renderer takes a DataFrame and returns the encoded image as bytes.
"""
from ._style import Format
from .consistency import consistency_aggregate, consistency_scatter
from .pickban_heat import pickban_heat
from .score_distribution import score_distribution

PLOTS: dict[str, str] = {
    "score_distribution":  "Score distribution (per map, KDE)",
    "pickban_heat":        "Pick / ban / protect heat",
    "consistency_scatter": "Player consistency",
}

__all__ = [
    "Format",
    "PLOTS",
    "score_distribution",
    "pickban_heat",
    "consistency_aggregate",
    "consistency_scatter",
]
