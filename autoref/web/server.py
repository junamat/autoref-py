"""Web interface: per-match WebInterface + shared WebServer registry."""
import asyncio
import json
import logging
import os
import uuid
from pathlib import Path

from ._state import _STATIC_DIR, _POOL_STORE

logger = logging.getLogger(__name__)


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
                 bancho_password: str | None = None,
                 db_path: str | Path | None = None):
        from ..core.storage import MatchDatabase
        self.host = host
        self.port = port
        self.static_dir = Path(static_dir) if static_dir else _STATIC_DIR
        self._matches: dict[str, WebInterface] = {}
        self._pending: dict[str, dict] = {}   # match_id -> raw payload, not yet started
        self._landing_clients: set = set()
        self._bancho_username = bancho_username or os.getenv("BANCHO_USERNAME", "")
        self._bancho_password = bancho_password or os.getenv("BANCHO_PASSWORD", "")
        self._tasks: dict[str, asyncio.Task] = {}
        # Single shared sqlite file for cross-match stats. Override path with $AUTOREF_DB.
        self.db = MatchDatabase(db_path or os.getenv("AUTOREF_DB", "matches.db"))

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
        from ..factory import build_autoref

        def _pool_loader(pool_id):
            return _POOL_STORE.get(pool_id)

        ar, client = await build_autoref(
            payload,
            bancho_username=self._bancho_username,
            bancho_password=self._bancho_password,
            pool_loader=_pool_loader,
            db=self.db,
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
        from fastapi import FastAPI
        from fastapi.staticfiles import StaticFiles
        import uvicorn

        from .routes import register_all

        app = FastAPI()
        app.mount("/static", StaticFiles(directory=self.static_dir), name="static")
        register_all(app, self)

        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="info")
        srv = uvicorn.Server(config)
        logger.info("web server at http://%s:%d", self.host, self.port)
        await srv.serve()
