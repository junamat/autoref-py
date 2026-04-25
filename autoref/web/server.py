"""WebInterface: live chat view and message input served over HTTP/WebSocket."""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).parent / "static"


class WebInterface:
    def __init__(self, host: str = "0.0.0.0", port: int = 8080,
                 static_dir: str | Path | None = None):
        self.host = host
        self.port = port
        self.static_dir = Path(static_dir) if static_dir else _STATIC_DIR
        self._clients: set = set()
        self._lobby = None
        self._last_state: dict | None = None

    def attach(self, lobby) -> None:
        self._lobby = lobby
        lobby.add_message_hook(self._on_message)

    def attach_autoref(self, ar) -> None:
        """Register state-push hook so all AutoRef state changes reach the UI."""
        ar.add_state_hook(self._on_state)

    # ---------------------------------------------------------------- hooks

    async def _on_message(self, username: str, message: str, outgoing: bool) -> None:
        if not self._clients:
            return
        payload = json.dumps({
            "type": "chat",
            "username": username,
            "message": message,
            "outgoing": outgoing,
        })
        await self._broadcast(payload)

    async def _on_state(self, state: dict) -> None:
        self._last_state = state
        if not self._clients:
            return
        await self._broadcast(json.dumps({"type": "state", **state}))

    async def _broadcast(self, payload: str) -> None:
        dead = set()
        for client in self._clients:
            try:
                await client.send_text(payload)
            except Exception:
                dead.add(client)
        self._clients -= dead

    # ---------------------------------------------------------------- server

    async def start(self) -> None:
        from fastapi import FastAPI, WebSocket, WebSocketDisconnect
        from fastapi.responses import FileResponse
        from fastapi.staticfiles import StaticFiles
        import uvicorn

        app = FastAPI()
        clients = self._clients
        static_dir = self.static_dir
        iface = self

        app.mount("/static", StaticFiles(directory=static_dir), name="static")

        @app.get("/")
        async def index():
            return FileResponse(static_dir / "index.html")

        @app.get("/api/status")
        async def api_status():
            from fastapi.responses import JSONResponse
            if iface._last_state:
                s = iface._last_state
                return JSONResponse({
                    "active": True,
                    "qualifier": s.get("qualifier", False),
                    "mode": s.get("mode", "off"),
                    "team_names": s.get("team_names", []),
                    "best_of": s.get("best_of"),
                    "ref_name": s.get("ref_name"),
                    "maps_played": s.get("maps_played"),
                    "total_maps": s.get("total_maps"),
                    "phase": s.get("phase"),
                })
            return JSONResponse({"active": False})

        @app.websocket("/ws")
        async def ws_endpoint(websocket: WebSocket):
            await websocket.accept()
            clients.add(websocket)
            if iface._last_state:
                try:
                    await websocket.send_text(
                        json.dumps({"type": "state", **iface._last_state})
                    )
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
                clients.discard(websocket)

        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="warning")
        server = uvicorn.Server(config)
        logger.info("web interface at http://%s:%d", self.host, self.port)
        await server.serve()
