"""Stat plots for the web UI.

Soft dependency: requires matplotlib + scipy (install via the [plots] extra).
Each renderer takes a DataFrame and returns the encoded image as bytes.
"""
from ._style import Format
from .action_sankey import action_sankey
from .comeback_rate import comeback_rate
from .consistency import consistency_aggregate, consistency_scatter
from .first_pick_frequency import first_pick_frequency
from .fm_mod_combo_stack import fm_mod_combo_stack
from .map_close_factor import map_close_factor
from .mod_popularity_timeline import mod_popularity_timeline
from .pick_and_win_rate import pick_and_win_rate
from .pickban_heat import pickban_heat
from .player_mod_radar import player_mod_radar
from .pp_consistency_scatter import pp_consistency_scatter
from .pp_vs_score_scatter import pp_vs_score_scatter
from .score_distribution import score_distribution
from .score_inflation_curve import score_inflation_curve
from .score_lead_trajectory import score_lead_trajectory
from .tb_incidence import tb_incidence
from .team_pool_heatmap import team_pool_heatmap
from .team_rank_distribution import team_rank_distribution
from .team_score_variance import team_score_variance
from .team_strategy_profile import team_strategy_profile
from .upset_rate_by_round import upset_rate_by_round

PLOTS: dict[str, str] = {
    "score_distribution":       "Score distribution (per map, KDE)",
    "pickban_heat":             "Pick / ban / protect heat",
    "consistency_scatter":      "Player consistency",
    "tb_incidence":             "Tiebreaker incidence per pool",
    "map_close_factor":         "Map closeness (blowout ↔ swing)",
    "pick_and_win_rate":        "Pick & win rate per map",
    "first_pick_frequency":     "First-pick frequency (opener maps)",
    "score_lead_trajectory":    "Score lead trajectory (drama envelope)",
    "comeback_rate":            "Comeback rate (trailing at half → wins)",
    "action_sankey":            "Action flow (top transitions)",
    "player_mod_radar":         "Player mod profile (mean z per bracket)",
    "team_rank_distribution":   "Team rank distribution (carry vs support)",
    "pp_vs_score_scatter":      "PP vs score scatter (mod sanity)",
    "pp_consistency_scatter":   "PP consistency scatter",
    "team_pool_heatmap":        "Team × pool heatmap (strength matrix)",
    "team_strategy_profile":    "Team strategy profile (actions by mod)",
    "team_score_variance":      "Team score variance (streaky vs steady)",
    "score_inflation_curve":    "Score inflation curve (meta progression)",
    "mod_popularity_timeline":  "Mod popularity timeline (meta evolution)",
    "fm_mod_combo_stack":       "FM mod combo stack (choices per slot)",
    "upset_rate_by_round":      "Upset rate by round (lower seed wins)",
}

__all__ = [
    "Format",
    "PLOTS",
    "action_sankey",
    "comeback_rate",
    "consistency_aggregate",
    "consistency_scatter",
    "first_pick_frequency",
    "fm_mod_combo_stack",
    "map_close_factor",
    "mod_popularity_timeline",
    "pick_and_win_rate",
    "pickban_heat",
    "player_mod_radar",
    "pp_consistency_scatter",
    "pp_vs_score_scatter",
    "score_distribution",
    "score_inflation_curve",
    "score_lead_trajectory",
    "tb_incidence",
    "team_pool_heatmap",
    "team_rank_distribution",
    "team_score_variance",
    "team_strategy_profile",
    "upset_rate_by_round",
]
