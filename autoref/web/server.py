"""Web interface: per-match WebInterface + shared WebServer registry."""
import json
import logging
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).parent / "static"


class WebInterface:
    """Attaches to one AutoRef instance; registered into a WebServer."""

    def __init__(self, match_id: str | None = None):
        self.match_id: str = match_id or str(uuid.uuid4())[:8]
        self._clients: set = set()
        self._lobby = None
        self._last_state: dict | None = None
        self._server: "WebServer | None" = None

    def attach(self, lobby) -> None:
        self._lobby = lobby
        lobby.add_message_hook(self._on_message)
        lobby.register_reply_sink("web", self._reply)

    def attach_autoref(self, ar) -> None:
        ar.add_state_hook(self._on_state)

    # ---------------------------------------------------------------- hooks

    async def _reply(self, text: str) -> None:
        """Reply sink: send text only to web clients (not to Bancho)."""
        await self._broadcast(json.dumps({"type": "reply", "text": text}))

    async def _on_message(self, username: str, message: str, outgoing: bool) -> None:
        await self._broadcast(json.dumps({
            "type": "chat",
            "username": username,
            "message": message,
            "outgoing": outgoing,
        }))

    async def _on_state(self, state: dict) -> None:
        self._last_state = state
        if self._server:
            self._server._notify_landing()
        await self._broadcast(json.dumps({"type": "state", **state}))

    async def _broadcast(self, payload: str) -> None:
        dead = set()
        for client in self._clients:
            try:
                await client.send_text(payload)
            except Exception:
                dead.add(client)
        self._clients -= dead

    def summary(self) -> dict:
        """Compact summary for /api/matches."""
        s = self._last_state or {}
        return {
            "id":          self.match_id,
            "active":      True,
            "qualifier":   s.get("qualifier", False),
            "mode":        s.get("mode", "off"),
            "team_names":  s.get("team_names", []),
            "best_of":     s.get("best_of"),
            "ref_name":    s.get("ref_name"),
            "maps_played": s.get("maps_played"),
            "total_maps":  s.get("total_maps"),
            "phase":       s.get("phase"),
        }


class WebServer:
    """Shared FastAPI server. Register WebInterface instances before calling start()."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8080,
                 static_dir: str | Path | None = None):
        self.host = host
        self.port = port
        self.static_dir = Path(static_dir) if static_dir else _STATIC_DIR
        self._matches: dict[str, WebInterface] = {}
        self._landing_clients: set = set()

    def register(self, iface: WebInterface) -> WebInterface:
        """Add a WebInterface to the registry. Returns the interface for chaining."""
        iface._server = self
        self._matches[iface.match_id] = iface
        return iface

    def unregister(self, iface: WebInterface) -> None:
        self._matches.pop(iface.match_id, None)

    def _notify_landing(self) -> None:
        """Push updated match list to all landing-page clients."""
        import asyncio
        payload = json.dumps({"type": "matches", "matches": [m.summary() for m in self._matches.values()]})
        dead = set()
        for client in self._landing_clients:
            try:
                asyncio.ensure_future(client.send_text(payload))
            except Exception:
                dead.add(client)
        self._landing_clients -= dead

    async def start(self) -> None:
        from fastapi import FastAPI, WebSocket, WebSocketDisconnect
        from fastapi.responses import FileResponse, JSONResponse
        from fastapi.staticfiles import StaticFiles
        import uvicorn

        app = FastAPI()
        server = self

        app.mount("/static", StaticFiles(directory=self.static_dir), name="static")

        @app.get("/")
        async def index():
            return FileResponse(self.static_dir / "index.html")

        @app.get("/api/matches")
        async def api_matches():
            return JSONResponse([m.summary() for m in server._matches.values()])

        @app.websocket("/ws/landing")
        async def ws_landing(websocket: WebSocket):
            await websocket.accept()
            server._landing_clients.add(websocket)
            # send current state immediately
            await websocket.send_text(json.dumps({
                "type": "matches",
                "matches": [m.summary() for m in server._matches.values()],
            }))
            try:
                while True:
                    await websocket.receive_text()  # keep alive
            except WebSocketDisconnect:
                pass
            finally:
                server._landing_clients.discard(websocket)

        @app.websocket("/ws/{match_id}")
        async def ws_match(websocket: WebSocket, match_id: str):
            iface = server._matches.get(match_id)
            if iface is None:
                await websocket.close(code=4004)
                return
            await websocket.accept()
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

        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="warning")
        srv = uvicorn.Server(config)
        logger.info("web server at http://%s:%d", self.host, self.port)
        await srv.serve()
