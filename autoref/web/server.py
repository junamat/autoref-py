"""Web interface: per-match WebInterface + shared WebServer registry."""
import asyncio
import json
import logging
import os
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).parent / "static"


_POOLS_FILE = Path.home() / ".cache" / "autoref" / "pools.json"


def _load_pools() -> dict:
    try:
        return json.loads(_POOLS_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_pools(pools: dict) -> None:
    _POOLS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _POOLS_FILE.write_text(json.dumps(pools, indent=2))



def _flatten_pool_tree(nodes: list, parent_mods: str = "") -> list:
    from .controllers.factory import flatten_pool_tree as _ft
    return _ft(nodes, parent_mods)


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
                 static_dir: str | Path | None = None,
                 bancho_username: str | None = None,
                 bancho_password: str | None = None):
        self.host = host
        self.port = port
        self.static_dir = Path(static_dir) if static_dir else _STATIC_DIR
        self._matches: dict[str, WebInterface] = {}
        self._pending: dict[str, dict] = {}   # match_id -> raw payload, not yet started
        self._landing_clients: set = set()
        self._bancho_username = bancho_username or os.getenv("BANCHO_USERNAME", "")
        self._bancho_password = bancho_password or os.getenv("BANCHO_PASSWORD", "")
        self._tasks: dict[str, asyncio.Task] = {}

    def register(self, iface: WebInterface) -> WebInterface:
        """Add a WebInterface to the registry. Returns the interface for chaining."""
        iface._server = self
        self._matches[iface.match_id] = iface
        return iface

    def unregister(self, iface: WebInterface) -> None:
        self._matches.pop(iface.match_id, None)
        self._tasks.pop(iface.match_id, None)
        asyncio.ensure_future(iface._broadcast(json.dumps({"type": "done"})))
        self._notify_landing()

    def _notify_landing(self) -> None:
        """Push updated match list to all landing-page clients."""
        all_matches = (
            [self._pending_summary(mid, p) for mid, p in self._pending.items()] +
            [m.summary() for m in self._matches.values()]
        )
        payload = json.dumps({"type": "matches", "matches": all_matches})
        dead = set()
        for client in self._landing_clients:
            try:
                asyncio.ensure_future(client.send_text(payload))
            except Exception:
                dead.add(client)
        self._landing_clients -= dead

    def _pending_summary(self, match_id: str, payload: dict) -> dict:
        teams = payload.get("teams", [])
        return {
            "id":         match_id,
            "status":     "pending",
            "qualifier":  payload.get("type") == "qualifiers",
            "mode":       payload.get("mode", "off"),
            "team_names": [t["name"] for t in teams],
            "best_of":    payload.get("best_of"),
        }

    async def _create_match(self, payload: dict, match_id: str | None = None) -> WebInterface:
        """Spin up an AutoRef from a web payload and register it."""
        from ..controllers.factory import build_autoref

        def _pool_loader(pool_id):
            return _load_pools().get(pool_id)

        ar, client = await build_autoref(
            payload,
            bancho_username=self._bancho_username,
            bancho_password=self._bancho_password,
            pool_loader=_pool_loader,
        )

        iface = WebInterface(match_id=match_id)
        self.register(iface)
        iface.attach(ar.lobby)
        iface.attach_autoref(ar)

        async def _run():
            try:
                await client.connect()
                await ar.run()
            except Exception:
                logger.exception("match %s crashed", iface.match_id)
            finally:
                await client.disconnect()
                self.unregister(iface)

        self._tasks[iface.match_id] = asyncio.create_task(_run())
        return iface

    async def start(self) -> None:
        from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
        from fastapi.responses import FileResponse, JSONResponse
        from fastapi.staticfiles import StaticFiles
        import uvicorn

        app = FastAPI()
        server = self

        app.mount("/static", StaticFiles(directory=self.static_dir), name="static")

        @app.get("/")
        async def index():
            return FileResponse(self.static_dir / "index.html")

        @app.get("/pool-builder")
        async def pool_builder():
            return FileResponse(self.static_dir / "pool_builder.html")

        @app.get("/api/pools")
        async def list_pools():
            return JSONResponse(list(_load_pools().values()))

        @app.post("/api/pools")
        async def save_pool(request: Request):
            try:
                body = await request.json()
                name = body.get("name", "").strip()
                if not name:
                    return JSONResponse({"error": "name required"}, status_code=400)
                pools = _load_pools()
                # use name as key (overwrite if same name)
                pool_id = body.get("id") or name.lower().replace(" ", "_")
                pools[pool_id] = {**body, "id": pool_id}
                _save_pools(pools)
                return JSONResponse({"id": pool_id}, status_code=201)
            except Exception as e:
                return JSONResponse({"error": str(e)}, status_code=500)

        @app.delete("/api/pools/{pool_id}")
        async def delete_pool(pool_id: str):
            pools = _load_pools()
            if pool_id not in pools:
                return JSONResponse({"error": "not found"}, status_code=404)
            del pools[pool_id]
            _save_pools(pools)
            return JSONResponse({"ok": True})

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

        @app.get("/match/{match_id}")
        async def match_view(match_id: str):
            return FileResponse(self.static_dir / "index.html")

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

        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="info")
        srv = uvicorn.Server(config)
        logger.info("web server at http://%s:%d", self.host, self.port)
        await srv.serve()
