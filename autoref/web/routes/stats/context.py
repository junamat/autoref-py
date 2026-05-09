from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from ...server import WebServer


def register(app: FastAPI, server: "WebServer") -> None:
    @app.get("/api/stats/context")
    async def api_stats_context(pool_id: str | None = None,
                                round_name: str | None = None):
        """Match-type context flags for the current filter scope.

        Returns:
            has_teams: True when any match_teams rows exist in scope.
            has_bracket: True when any BAN/PROTECT actions exist in scope.
        """
        return JSONResponse(server.db.context(pool_id=pool_id, round_name=round_name))
