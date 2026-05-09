from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Literal, cast

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from ._common import _build_map_code_lookup

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
        try:
            if name == "score_distribution":
                if beatmap_id is None:
                    return JSONResponse({"error": "beatmap_id required"}, status_code=400)
                if label is None:
                    label = _build_map_code_lookup().get(int(beatmap_id))
                payload = _plots.score_distribution(
                    scores, int(beatmap_id), fmt=fmt, theme=theme,
                    exclude_failed=not count_failed, label=label,
                )
            elif name == "pickban_heat":
                payload = _plots.pickban_heat(
                    server.db.get_map_action_breakdown(pool_id=pool_id, round_name=round_name),
                    fmt=fmt, theme=theme,
                    code_by_bid=_build_map_code_lookup(),
                )
            elif name == "consistency_scatter":
                payload = _plots.consistency_scatter(
                    scores, fmt=fmt, theme=theme,
                    exclude_failed=not count_failed,
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
