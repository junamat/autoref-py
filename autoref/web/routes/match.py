"""Match lifecycle routes."""
import logging
import uuid
from typing import TYPE_CHECKING

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from ..server import WebServer

logger = logging.getLogger(__name__)


def register(app: FastAPI, server: "WebServer") -> None:
    from .._auth_dep import require_login

    @app.get("/api/matches")
    async def api_matches():
        all_matches = (
            [server._pending_summary(mid, p) for mid, p in server._pending.items()] +
            [m.summary() for m in server._matches.values()]
        )
        return JSONResponse(all_matches)

    @app.post("/api/matches")
    async def create_match(request: Request, user=Depends(require_login)):
        if not user.irc_username:
            return JSONResponse({"error": "missing_irc", "field": "irc_username"}, status_code=400)
        if not user.irc_password:
            return JSONResponse({"error": "missing_irc", "field": "irc_password"}, status_code=400)
        try:
            body = await request.json()
            match_id = str(uuid.uuid4())[:8]
            server._pending[match_id] = {
                **body,
                "_bancho_username": user.irc_username,
                "_bancho_password": user.irc_password,
            }
            server._notify_landing()
            return JSONResponse({"id": match_id, "status": "pending"}, status_code=201)
        except Exception as e:
            logger.exception("failed to create match")
            return JSONResponse({"error": str(e)}, status_code=500)

    @app.post("/api/matches/{match_id}/start")
    async def start_match(match_id: str, user=Depends(require_login)):
        payload = server._pending.pop(match_id, None)
        if payload is None:
            return JSONResponse({"error": "not found or already started"}, status_code=404)
        bancho_username = payload.pop("_bancho_username", None)
        bancho_password = payload.pop("_bancho_password", None)
        try:
            iface = await server._create_match(
                payload, match_id=match_id,
                bancho_username=bancho_username,
                bancho_password=bancho_password,
            )
            return JSONResponse({"id": iface.match_id, "status": "running"})
        except Exception as e:
            server._pending[match_id] = payload  # restore on failure
            logger.exception("failed to start match")
            return JSONResponse({"error": str(e)}, status_code=500)

    @app.delete("/api/matches/{match_id}")
    async def delete_match(match_id: str, user=Depends(require_login)):
        if match_id in server._pending:
            del server._pending[match_id]
            server._notify_landing()
            return JSONResponse({"ok": True})
        iface = server._matches.get(match_id)
        if iface is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        if iface._lobby:
            await iface._lobby.handle_input(">close force", "web")
        return JSONResponse({"ok": True})

    @app.post("/api/matches/{match_id}/resume")
    async def resume_match(match_id: str, request: Request, user=Depends(require_login)):
        row = server._pending_resume.get(match_id)
        if row is None:
            return JSONResponse({"error": "not found or not an orphan"}, status_code=404)
        owner_id = row.get("owner_user_id")
        if owner_id is not None and owner_id != user.id and user.role != "host":
            return JSONResponse({"error": "forbidden"}, status_code=403)
        # Remove from orphan list; it will be re-added if it crashes again
        server._pending_resume.pop(match_id, None)
        server._notify_landing()
        try:
            iface = await server._resume_match(
                row,
                bancho_username=user.irc_username,
                bancho_password=user.irc_password,
            )
            return JSONResponse({"id": iface.match_id, "status": "running"})
        except Exception as e:
            logger.exception("failed to resume match %s", match_id)
            server._pending_resume[match_id] = row
            return JSONResponse({"error": str(e)}, status_code=500)

    @app.delete("/api/matches/{match_id}/resume")
    async def discard_orphan(match_id: str, user=Depends(require_login)):
        row = server._pending_resume.get(match_id)
        if row is None:
            return JSONResponse({"error": "not found or not an orphan"}, status_code=404)
        owner_id = row.get("owner_user_id")
        if owner_id is not None and owner_id != user.id and user.role != "host":
            return JSONResponse({"error": "forbidden"}, status_code=403)
        server.db.update_live_match_status(match_id, "crashed")
        server._pending_resume.pop(match_id, None)
        server._notify_landing()
        return JSONResponse({"ok": True})
