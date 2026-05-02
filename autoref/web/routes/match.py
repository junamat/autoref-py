"""Match lifecycle routes."""
import logging
import uuid
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from ..server import WebServer

logger = logging.getLogger(__name__)


def register(app: FastAPI, server: "WebServer") -> None:
    @app.get("/api/matches")
    async def api_matches():
        all_matches = (
            [server._pending_summary(mid, p) for mid, p in server._pending.items()] +
            [m.summary() for m in server._matches.values()]
        )
        return JSONResponse(all_matches)

    @app.post("/api/matches")
    async def create_match(request: Request):
        try:
            body = await request.json()
            match_id = str(uuid.uuid4())[:8]
            server._pending[match_id] = body
            server._notify_landing()
            return JSONResponse({"id": match_id, "status": "pending"}, status_code=201)
        except Exception as e:
            logger.exception("failed to create match")
            return JSONResponse({"error": str(e)}, status_code=500)

    @app.post("/api/matches/{match_id}/start")
    async def start_match(match_id: str, request: Request):
        payload = server._pending.pop(match_id, None)
        if payload is None:
            return JSONResponse({"error": "not found or already started"}, status_code=404)
        try:
            iface = await server._create_match(payload, match_id=match_id)
            return JSONResponse({"id": iface.match_id, "status": "running"})
        except Exception as e:
            server._pending[match_id] = payload  # restore on failure
            logger.exception("failed to start match")
            return JSONResponse({"error": str(e)}, status_code=500)

    @app.delete("/api/matches/{match_id}")
    async def delete_match(match_id: str):
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
