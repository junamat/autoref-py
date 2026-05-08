"""Web interface: per-match WebInterface + shared WebServer registry."""
import asyncio
import json
import logging
import os
import uuid
from pathlib import Path

from ._state import _POOL_STORE, _STATIC_DIR

logger = logging.getLogger(__name__)

_BACKOFF = [2, 4, 8, 16, 32, 60, 120, 300]


class WebInterface:
    """Attaches to one AutoRef instance; registered into a WebServer."""

    def __init__(self, match_id: str | None = None):
        self.match_id: str = match_id or str(uuid.uuid4())[:8]
        self._clients: set = set()
        self._lobby = None
        self._autoref = None
        self._last_state: dict | None = None
        self._server: "WebServer | None" = None

    def attach(self, lobby) -> None:
        self._lobby = lobby
        lobby.add_message_hook(self._on_message)
        lobby.register_reply_sink("web", self._reply)

    def attach_autoref(self, ar) -> None:
        self._autoref = ar
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
            self._server._schedule_snapshot(self.match_id)
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

    def __init__(self, host: str | None = None, port: int | None = None,
                 static_dir: str | Path | None = None,
                 db_path: str | Path | None = None):
        from ..core.config import load as load_config
        from ..core.storage import MatchDatabase
        self.static_dir = Path(static_dir) if static_dir else _STATIC_DIR
        self._matches: dict[str, WebInterface] = {}
        self._pending: dict[str, dict] = {}       # match_id -> raw payload, not yet started
        self._pending_resume: dict[str, dict] = {}  # match_id -> live_matches row
        self._landing_clients: set = set()
        self._tasks: dict[str, asyncio.Task] = {}
        self._snapshot_tasks: dict[str, asyncio.Task] = {}
        self._match_metadata: dict[str, dict] = {}  # match_id -> {owner_user_id, controller_type, payload_json}
        self.db = MatchDatabase(db_path if db_path is not None else os.getenv("AUTOREF_DB", "matches.db"))
        self.config = load_config(self.db)
        self.host = host if host is not None else self.config.host
        self.port = port if port is not None else self.config.port

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
            [m.summary() for m in self._matches.values()] +
            [self._orphan_summary(row) for row in self._pending_resume.values()]
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

    def _orphan_summary(self, row: dict) -> dict:
        payload = json.loads(row.get("payload_json") or "{}")
        teams = payload.get("teams", [])
        return {
            "id":             row["match_id"],
            "status":         row.get("status", "orphaned"),
            "orphaned":       True,
            "qualifier":      payload.get("type") == "qualifiers",
            "controller_type": row.get("controller_type"),
            "team_names":     [t["name"] for t in teams],
            "best_of":        payload.get("best_of"),
            "bancho_lobby_id": row.get("bancho_lobby_id"),
            "orphaned_since": row.get("updated_at"),
        }

    # --------------------------------------------------------- snapshot writer (T37)

    def _schedule_snapshot(self, match_id: str) -> None:
        existing = self._snapshot_tasks.get(match_id)
        if existing and not existing.done():
            existing.cancel()
        self._snapshot_tasks[match_id] = asyncio.ensure_future(
            self._write_snapshot(match_id, delay=1.0)
        )

    async def _write_snapshot(self, match_id: str, delay: float = 1.0) -> None:
        await asyncio.sleep(delay)
        iface = self._matches.get(match_id)
        if iface is None or iface._autoref is None:
            return
        ar = iface._autoref
        meta = self._match_metadata.get(match_id, {})
        try:
            state_json = json.dumps(ar.to_state_dict())
        except Exception:
            logger.exception("snapshot serialisation failed for %s", match_id)
            return
        self.db.upsert_live_match(
            match_id,
            owner_user_id=meta.get("owner_user_id"),
            controller_type=meta.get("controller_type"),
            payload_json=meta.get("payload_json"),
            state_json=state_json,
            bancho_lobby_id=ar.lobby.room_id,
            status="running",
        )

    async def _create_match(self, payload: dict, match_id: str | None = None,
                            bancho_username: str | None = None,
                            bancho_password: str | None = None,
                            owner_user_id: int | None = None) -> WebInterface:
        """Spin up an AutoRef from a web payload and register it."""
        from ..factory import build_autoref

        def _pool_loader(pool_id):
            return _POOL_STORE.get(pool_id)

        ar, client = await build_autoref(
            payload,
            bancho_username=bancho_username or self.config.bancho_username,
            bancho_password=bancho_password or self.config.bancho_password,
            pool_loader=_pool_loader,
            db=self.db,
            defaults=self.config,
        )

        iface = WebInterface(match_id=match_id)
        self.register(iface)
        iface.attach(ar.lobby)
        iface.attach_autoref(ar)

        controller_type = type(ar).__name__
        payload_json_str = json.dumps(payload)
        mid = iface.match_id
        self._match_metadata[mid] = {
            "owner_user_id": owner_user_id,
            "controller_type": controller_type,
            "payload_json": payload_json_str,
        }
        self.db.upsert_live_match(
            mid,
            owner_user_id=owner_user_id,
            controller_type=controller_type,
            payload_json=payload_json_str,
            status="pending",
        )

        async def _run():
            attempt = 0
            resume = False
            while True:
                try:
                    await client.connect()
                    self.db.update_live_match_status(mid, "running")
                    await ar.run(resume=resume)
                    self.db.update_live_match_status(mid, "finished")
                    break
                except Exception:
                    logger.exception("match %s disconnected/crashed (attempt %d)", mid, attempt)
                    self.db.update_live_match_status(mid, "orphaned")
                    self._pending_resume[mid] = self.db.get_orphaned_live_matches()
                    # refresh pending_resume with the single row
                    rows = self.db.get_orphaned_live_matches()
                    row = next((r for r in rows if r["match_id"] == mid), None)
                    if row:
                        self._pending_resume[mid] = row
                    self._notify_landing()
                    delay = _BACKOFF[min(attempt, len(_BACKOFF) - 1)]
                    attempt += 1
                    logger.info("match %s: retry in %ds", mid, delay)
                    await asyncio.sleep(delay)
                    try:
                        await client.disconnect()
                    except Exception:
                        pass
                    resume = True
                    continue
            await client.disconnect()
            self.unregister(iface)
            self._pending_resume.pop(mid, None)
            self._match_metadata.pop(mid, None)

        self._tasks[iface.match_id] = asyncio.create_task(_run())
        return iface

    async def _resume_match(self, row: dict,
                            bancho_username: str | None = None,
                            bancho_password: str | None = None) -> WebInterface:
        """Hydrate an orphaned match and resume it."""
        from ..factory import build_autoref

        match_id = row["match_id"]
        payload = json.loads(row.get("payload_json") or "{}")
        state_d = json.loads(row.get("state_json") or "{}")
        owner_user_id = row.get("owner_user_id")

        def _pool_loader(pool_id):
            return _POOL_STORE.get(pool_id)

        ar, client = await build_autoref(
            payload,
            bancho_username=bancho_username or self.config.bancho_username,
            bancho_password=bancho_password or self.config.bancho_password,
            pool_loader=_pool_loader,
            db=self.db,
            defaults=self.config,
        )
        ar.from_state_dict(state_d)

        iface = WebInterface(match_id=match_id)
        self.register(iface)
        iface.attach(ar.lobby)
        iface.attach_autoref(ar)

        controller_type = type(ar).__name__
        payload_json_str = json.dumps(payload)
        self._match_metadata[match_id] = {
            "owner_user_id": owner_user_id,
            "controller_type": controller_type,
            "payload_json": payload_json_str,
        }

        mid = match_id

        async def _run():
            attempt = 0
            resume = True
            while True:
                try:
                    await client.connect()
                    self.db.update_live_match_status(mid, "running")
                    await ar.run(resume=resume)
                    self.db.update_live_match_status(mid, "finished")
                    break
                except Exception:
                    logger.exception("match %s disconnected/crashed (attempt %d)", mid, attempt)
                    self.db.update_live_match_status(mid, "orphaned")
                    rows = self.db.get_orphaned_live_matches()
                    row2 = next((r for r in rows if r["match_id"] == mid), None)
                    if row2:
                        self._pending_resume[mid] = row2
                    self._notify_landing()
                    delay = _BACKOFF[min(attempt, len(_BACKOFF) - 1)]
                    attempt += 1
                    logger.info("match %s: retry in %ds", mid, delay)
                    await asyncio.sleep(delay)
                    try:
                        await client.disconnect()
                    except Exception:
                        pass
                    resume = True
                    continue
            await client.disconnect()
            self.unregister(iface)
            self._pending_resume.pop(mid, None)
            self._match_metadata.pop(mid, None)

        self._tasks[match_id] = asyncio.create_task(_run())
        return iface

    async def start(self) -> None:
        import uvicorn
        from fastapi import FastAPI
        from fastapi.staticfiles import StaticFiles

        from ._gate import SetupGateMiddleware
        from .routes import register_all

        # T38: load orphaned matches into pending-resume list (NOT auto-resumed)
        for row in self.db.get_orphaned_live_matches():
            self._pending_resume[row["match_id"]] = row

        app = FastAPI()
        app.state.db = self.db
        app.mount("/static", StaticFiles(directory=self.static_dir), name="static")
        register_all(app, self)
        app.add_middleware(SetupGateMiddleware, db=self.db)

        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="info")
        srv = uvicorn.Server(config)
        logger.info("web server at http://%s:%d", self.host, self.port)
        await srv.serve()
