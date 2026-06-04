"""MP link import routes."""
import logging
from typing import TYPE_CHECKING

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from ..server import WebServer

logger = logging.getLogger(__name__)


def register(app: FastAPI, server: "WebServer") -> None:
    from ...client import make_client
    from ...core.mp_importer import fetch_mp_match, save_imported_match_with_pp
    from ...core.mp_link import parse_mp_link
    from .._auth_dep import require_not_player

    @app.post("/api/mp/preview")
    async def preview_mp_link(request: Request, user=Depends(require_not_player)):
        """Fetch match data from MP link and return preview with inferred teams."""
        try:
            body = await request.json()
            url = body.get("url", "")

            mp_link = parse_mp_link(url)
            if mp_link is None:
                return JSONResponse({"error": "invalid_mp_link"}, status_code=400)

            async with make_client() as client:
                imported = await fetch_mp_match(client, mp_link)

            if not imported.games:
                return JSONResponse({"error": "no_games_found"}, status_code=400)

            sorted_users = sorted(imported.users.items())
            players = [
                {"user_id": uid, "username": uname, "team_index": i, "enabled": True}
                for i, (uid, uname) in enumerate(sorted_users)
            ]

            games = [
                {
                    "beatmap_id": g.beatmap_id,
                    "num_scores": len(g.scores),
                }
                for g in imported.games
            ]

            return JSONResponse({
                "match_id": imported.match_id,
                "name": imported.name,
                "match_type": imported.match_type,
                "num_games": len(imported.games),
                "players": players,
                "games": games,
            })

        except Exception:
            logger.exception("failed to preview mp link")
            return JSONResponse({"error": "internal_error"}, status_code=500)

    @app.post("/api/mp/import")
    async def import_mp_link(request: Request, user=Depends(require_not_player)):
        """Import match with confirmed team assignments."""
        try:
            body = await request.json()
            url = body.get("url", "")
            players = body.get("players", [])
            pool_id = body.get("pool_id")
            round_name = body.get("round_name")

            mp_link = parse_mp_link(url)
            if mp_link is None:
                return JSONResponse({"error": "invalid_mp_link"}, status_code=400)

            async with make_client() as client:
                imported = await fetch_mp_match(client, mp_link)

            if not imported.games:
                return JSONResponse({"error": "no_games_found"}, status_code=400)

            enabled_players = {p["user_id"]: p for p in players if p.get("enabled", True)}

            filtered_games = []
            for game in imported.games:
                filtered_scores = [
                    s for s in game.scores
                    if s["user_id"] in enabled_players
                ]
                if filtered_scores:
                    from ...core.mp_importer import ImportedGame
                    filtered_games.append(ImportedGame(
                        beatmap_id=game.beatmap_id,
                        scores=filtered_scores,
                        start_time=game.start_time,
                        end_time=game.end_time,
                    ))

            if not filtered_games:
                return JSONResponse({"error": "no_valid_scores"}, status_code=400)

            imported.games = filtered_games
            imported.users = {
                uid: uname for uid, uname in imported.users.items()
                if uid in enabled_players
            }

            mid = await save_imported_match_with_pp(
                server.db,
                imported,
                pool_id=pool_id,
                round_name=round_name,
            )

            return JSONResponse({
                "match_id": mid,
                "imported": True,
                "num_games": len(filtered_games),
                "num_players": len(enabled_players),
            })

        except Exception:
            logger.exception("failed to import mp link")
            return JSONResponse({"error": "internal_error"}, status_code=500)

    @app.delete("/api/mp/imported/{match_id}")
    async def delete_imported_match(match_id: int, user=Depends(require_not_player)):
        """Delete an imported match and all associated data from the database."""
        deleted = server.db.matches.delete_match(match_id)
        if not deleted:
            return JSONResponse({"error": "not_found"}, status_code=404)
        return JSONResponse({"ok": True, "deleted": match_id})
