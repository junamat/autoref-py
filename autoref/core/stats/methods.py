"""Leaderboard method registry and DISPATCH table.

All algorithm implementations live in `leaderboards/`; this module re-exports
them for backward-compatibility and exposes METHODS + PP_METHODS + DISPATCH.
"""
from __future__ import annotations

from .leaderboards import (
    augment_pp,
    avg_placements_leaderboard,
    avg_score_leaderboard,
    beta_distribution_leaderboard,
    match_cost_bathbot_leaderboard,
    match_cost_flashlight_leaderboard,
    pct_diff_leaderboard,
    percentile_leaderboard,
    pp_leaderboard,
    z_pp_leaderboard,
    z_sum_leaderboard,
    zipf_leaderboard,
)

METHODS: dict[str, tuple[str, bool]] = {
    "zscore":        ("Z-Score",                   False),
    "avg_score":     ("Average Score",             False),
    "placements":    ("Placements",                True),
    "percentile":    ("Percentile",                False),
    "zipf":          ("Zipf's Law",                False),
    "pct_diff":      ("Percent Difference",        False),
    "mc_flashlight": ("Match Cost (Flashlight)",   False),
    "beta_dist":     ("Beta Distribution",         False),
    "pp":            ("Performance Points",        False),
    "z_pp":          ("Z-PP",                      False),
}

PP_METHODS: frozenset[str] = frozenset({"pp", "z_pp"})

DISPATCH: dict = {
    "zscore":        z_sum_leaderboard,
    "avg_score":     avg_score_leaderboard,
    "placements":    avg_placements_leaderboard,
    "percentile":    percentile_leaderboard,
    "zipf":          zipf_leaderboard,
    "pct_diff":      pct_diff_leaderboard,
    "mc_flashlight": match_cost_flashlight_leaderboard,
    "mc_bathbot":    match_cost_bathbot_leaderboard,
    "beta_dist":     beta_distribution_leaderboard,
    "pp":            pp_leaderboard,
    "z_pp":          z_pp_leaderboard,
}

__all__ = [
    "METHODS",
    "PP_METHODS",
    "DISPATCH",
    "z_sum_leaderboard",
    "avg_score_leaderboard",
    "avg_placements_leaderboard",
    "percentile_leaderboard",
    "zipf_leaderboard",
    "pct_diff_leaderboard",
    "match_cost_flashlight_leaderboard",
    "match_cost_bathbot_leaderboard",
    "beta_distribution_leaderboard",
    "pp_leaderboard",
    "z_pp_leaderboard",
    "augment_pp",
]
