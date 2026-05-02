"""Cross-match statistics over `game_scores` rows.

Pure pandas — fed by `MatchDatabase.get_all_scores()` (or any equivalent DataFrame).

A "score predicate" decides which rows count toward the population for a given
metric. Two stock predicates are provided; pass any callable(row_dict) -> bool.
"""
from .aggregate import aggregate_to_teams, team_leaderboard
from .leaderboard import leaderboard, leaderboard_async
from .methods import (
    METHODS,
    PP_METHODS,
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
from .predicates import ScorePredicate, exclude_failed, include_all

__all__ = [
    "ScorePredicate",
    "include_all",
    "exclude_failed",
    "METHODS",
    "PP_METHODS",
    "leaderboard",
    "leaderboard_async",
    "aggregate_to_teams",
    "team_leaderboard",
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
