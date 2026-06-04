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

    @app.get("/api/stats/matches")
    async def api_stats_matches():
        """List all imported matches with basic metadata."""
        history = server.db.get_match_history()
        matches = []
        for _, row in history.iterrows():
            matches.append({
                "match_id": int(row["match_id"]),
                "pool_id": row.get("pool_id"),
                "round_name": row.get("round_name"),
                "best_of": int(row.get("best_of", 0)),
                "winner_team": row.get("winner_team"),
            })
        return JSONResponse({"matches": matches})
