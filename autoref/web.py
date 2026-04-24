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

    def attach(self, lobby) -> None:
        self._lobby = lobby
        lobby.add_message_hook(self._on_message)

    async def _on_message(self, username: str, message: str, outgoing: bool) -> None:
        if not self._clients:
            return
        payload = json.dumps({"username": username, "message": message, "outgoing": outgoing})
        dead = set()
        for client in self._clients:
            try:
                await client.send_text(payload)
            except Exception:
                dead.add(client)
        self._clients -= dead

    async def start(self) -> None:
        from fastapi import FastAPI, WebSocket, WebSocketDisconnect
        from fastapi.responses import FileResponse
        from fastapi.staticfiles import StaticFiles
        import uvicorn

        app = FastAPI()
        clients = self._clients
        static_dir = self.static_dir

        app.mount("/static", StaticFiles(directory=static_dir), name="static")

        @app.get("/")
        async def index():
            return FileResponse(static_dir / "index.html")

        @app.websocket("/ws")
        async def ws_endpoint(websocket: WebSocket):
            await websocket.accept()
            clients.add(websocket)
            try:
                while True:
                    text = await websocket.receive_text()
                    if self._lobby:
                        await self._lobby.handle_input(text, "web")
            except WebSocketDisconnect:
                pass
            finally:
                clients.discard(websocket)

        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="warning")
        server = uvicorn.Server(config)
        logger.info("web interface at http://%s:%d", self.host, self.port)
        await server.serve()
