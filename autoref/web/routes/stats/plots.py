from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Literal, cast

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from ._common import _build_map_code_lookup, _build_map_mod_group_lookup

if TYPE_CHECKING:
    from ...server import WebServer

logger = logging.getLogger(__name__)


def register(app: FastAPI, server: "WebServer") -> None:
    @app.get("/api/stats/plot/{name}")
    async def api_stats_plot(name: str, format: str = "png", theme: str = "dark",
                             count_failed: bool = True, beatmap_id: int | None = None,
                             label: str | None = None,
                             pool_id: str | None = None, round_name: str | None = None):
        _plots: Any = None
        try:
            from .... import plots as _plots
        except ImportError:
            pass
        if _plots is None:
            return JSONResponse(
                {"error": "plot rendering requires the [plots] extra (pip install -e '.[plots]')"},
                status_code=501,
            )
        if format not in ("png", "hires", "svg"):
            return JSONResponse({"error": "format must be png|hires|svg"}, status_code=400)
        fmt = cast(Literal["png", "hires", "svg"], format)
        if name not in _plots.PLOTS:
            return JSONResponse(
                {"error": f"unknown plot {name!r}; choose from {list(_plots.PLOTS)}"},
                status_code=404,
            )
        theme = theme if theme in ("dark", "light") else "dark"

        scores = server.db.get_all_scores(pool_id=pool_id, round_name=round_name)
        code_by_bid = _build_map_code_lookup()
        mod_by_bid = _build_map_mod_group_lookup()
        try:
            if name == "score_distribution":
                if beatmap_id is None:
                    return JSONResponse({"error": "beatmap_id required"}, status_code=400)
                if label is None:
                    label = code_by_bid.get(int(beatmap_id))
                payload = _plots.score_distribution(
                    scores, int(beatmap_id), fmt=fmt, theme=theme,
                    exclude_failed=not count_failed, label=label,
                )
            elif name == "pickban_heat":
                payload = _plots.pickban_heat(
                    server.db.get_map_action_breakdown(pool_id=pool_id, round_name=round_name),
                    fmt=fmt, theme=theme, code_by_bid=code_by_bid,
                )
            elif name == "consistency_scatter":
                payload = _plots.consistency_scatter(
                    scores, fmt=fmt, theme=theme,
                    exclude_failed=not count_failed,
                )
            elif name == "tb_incidence":
                payload = _plots.tb_incidence(
                    server.db.get_tb_incidence(pool_id=pool_id, round_name=round_name),
                    fmt=fmt, theme=theme,
                )
            elif name == "map_close_factor":
                # Try team match format first, fall back to FFA format for qualifiers
                team_data = server.db.get_map_team_scores(pool_id=pool_id, round_name=round_name)
                if team_data.empty:
                    # FFA qualifiers: use all scores with beatmap_id and score columns
                    all_scores = server.db.get_all_scores(pool_id=pool_id, round_name=round_name)
                    if not all_scores.empty:
                        data = all_scores[["beatmap_id", "score"]].copy()
                    else:
                        data = team_data
                else:
                    data = team_data
                payload = _plots.map_close_factor(
                    data,
                    fmt=fmt, theme=theme, code_by_bid=code_by_bid,
                )
            elif name == "pick_and_win_rate":
                payload = _plots.pick_and_win_rate(
                    server.db.get_pick_win_rates(pool_id=pool_id, round_name=round_name),
                    fmt=fmt, theme=theme, code_by_bid=code_by_bid,
                )
            elif name == "first_pick_frequency":
                payload = _plots.first_pick_frequency(
                    server.db.get_first_picks(pool_id=pool_id, round_name=round_name),
                    fmt=fmt, theme=theme, code_by_bid=code_by_bid,
                )
            elif name == "score_lead_trajectory":
                payload = _plots.score_lead_trajectory(
                    server.db.get_score_turn_totals(pool_id=pool_id, round_name=round_name),
                    fmt=fmt, theme=theme,
                )
            elif name == "comeback_rate":
                payload = _plots.comeback_rate(
                    server.db.get_score_turn_totals(pool_id=pool_id, round_name=round_name),
                    fmt=fmt, theme=theme,
                )
            elif name == "action_sankey":
                payload = _plots.action_sankey(
                    server.db.get_all_actions_ordered(pool_id=pool_id, round_name=round_name),
                    fmt=fmt, theme=theme, mod_group_by_bid=mod_by_bid,
                )
            elif name == "player_mod_radar":
                payload = _plots.player_mod_radar(
                    scores, fmt=fmt, theme=theme,
                    mod_group_by_bid=mod_by_bid,
                    exclude_failed=not count_failed,
                )
            elif name == "team_rank_distribution":
                payload = _plots.team_rank_distribution(
                    scores, fmt=fmt, theme=theme,
                    exclude_failed=not count_failed,
                )
            elif name == "pp_vs_score_scatter":
                from ....core.stats.leaderboards.pp import augment_pp
                scores_with_pp = await augment_pp(scores, db=server.db)
                payload = _plots.pp_vs_score_scatter(
                    scores_with_pp, fmt=fmt, theme=theme,
                )
            elif name == "pp_consistency_scatter":
                from ....core.stats.leaderboards.pp import augment_pp
                scores_with_pp = await augment_pp(scores, db=server.db)
                payload = _plots.pp_consistency_scatter(
                    scores_with_pp, fmt=fmt, theme=theme,
                    exclude_failed=not count_failed,
                )
            elif name == "team_pool_heatmap":
                payload = _plots.team_pool_heatmap(
                    server.db.get_team_pool_scores(pool_id=pool_id, round_name=round_name),
                    fmt=fmt, theme=theme,
                )
            elif name == "team_strategy_profile":
                payload = _plots.team_strategy_profile(
                    server.db.get_all_actions_ordered(pool_id=pool_id, round_name=round_name),
                    fmt=fmt, theme=theme, mod_group_by_bid=mod_by_bid,
                )
            elif name == "team_score_variance":
                payload = _plots.team_score_variance(
                    server.db.get_map_team_scores(pool_id=pool_id, round_name=round_name),
                    fmt=fmt, theme=theme,
                )
            elif name == "score_inflation_curve":
                payload = _plots.score_inflation_curve(
                    server.db.get_scores_with_round(pool_id=pool_id, round_name=round_name),
                    fmt=fmt, theme=theme,
                )
            elif name == "mod_popularity_timeline":
                payload = _plots.mod_popularity_timeline(
                    server.db.get_pick_actions(pool_id=pool_id, round_name=round_name),
                    fmt=fmt, theme=theme, mod_group_by_bid=mod_by_bid,
                )
            elif name == "fm_mod_combo_stack":
                payload = _plots.fm_mod_combo_stack(
                    server.db.get_scores_with_round(pool_id=pool_id, round_name=round_name),
                    fmt=fmt, theme=theme, mod_group_by_bid=mod_by_bid,
                )
            elif name == "upset_rate_by_round":
                payload = _plots.upset_rate_by_round(
                    server.db.get_upset_data(pool_id=pool_id, round_name=round_name),
                    fmt=fmt, theme=theme,
                )
            else:
                return JSONResponse({"error": f"unknown plot {name}"}, status_code=404)
        except Exception:
            logger.exception("plot %s failed", name)
            return JSONResponse({"error": "internal_error"}, status_code=500)

        media_type = "image/svg+xml" if format == "svg" else "image/png"
        ext = "svg" if format == "svg" else "png"
        headers = {}
        if format in ("hires", "svg"):
            headers["content-disposition"] = f'attachment; filename="{name}.{ext}"'
        from fastapi.responses import Response
        return Response(content=payload, media_type=media_type, headers=headers)

    @app.get("/api/stats/plot/consistency_scatter/data")
    async def api_stats_consistency_data(count_failed: bool = True,
                                         pool_id: str | None = None,
                                         round_name: str | None = None):
        try:
            from .... import plots as _plots
        except ImportError:
            return JSONResponse({"error": "plot module unavailable"}, status_code=501)
        scores = server.db.get_all_scores(pool_id=pool_id, round_name=round_name)
        agg = _plots.consistency_aggregate(scores, exclude_failed=not count_failed)
        if agg.empty:
            return JSONResponse({"points": []})
        points = [
            {
                "user_id": int(r["user_id"]),
                "username": str(r["username"]),
                "mean_z": float(r["mean_z"]),
                "std_z": float(r["std_z"]),
                "n": int(r["n"]),
            }
            for _, r in agg.iterrows()
        ]
        std_median = float(agg["std_z"].median()) if len(agg) > 1 else None
        return JSONResponse({"points": points, "std_median": std_median})

    @app.get("/api/stats/plots")
    async def api_stats_plot_list():
        try:
            from .... import plots as _plots
        except ImportError:
            _plots = None
        if _plots is None:
            return JSONResponse({"available": False, "plots": []})
        return JSONResponse({
            "available": True,
            "plots": [{"name": k, "label": v} for k, v in _plots.PLOTS.items()],
        })
