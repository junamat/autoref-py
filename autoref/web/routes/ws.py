"""WebSocket routes."""
import json
from typing import TYPE_CHECKING

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

if TYPE_CHECKING:
    from ..server import WebServer


def register(app: FastAPI, server: "WebServer") -> None:
    @app.websocket("/ws/landing")
    async def ws_landing(websocket: WebSocket):
        await websocket.accept()
        server._landing_clients.add(websocket)
        await websocket.send_text(json.dumps({
            "type": "matches",
            "matches": [m.summary() for m in server._matches.values()],
        }))
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            server._landing_clients.discard(websocket)

    @app.websocket("/ws/{match_id}")
    async def ws_match(websocket: WebSocket, match_id: str):
        await websocket.accept()
        iface = server._matches.get(match_id)
        if iface is None:
            await websocket.send_text(json.dumps({"type": "error", "message": "match not found"}))
            await websocket.close(code=4004)
            return
        iface._clients.add(websocket)
        if iface._last_state:
            try:
                await websocket.send_text(json.dumps({"type": "state", **iface._last_state}))
            except Exception:
                pass
        try:
            while True:
                text = await websocket.receive_text()
                if iface._lobby:
                    await iface._lobby.handle_input(text, "web")
        except WebSocketDisconnect:
            pass
        finally:
            iface._clients.discard(websocket)
