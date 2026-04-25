"""Web interface: per-match WebInterface + shared WebServer registry."""
import asyncio
import json
import logging
import os
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
        import bancho
        import aiosu
        from ..core.models import Match, Pool, PlayableMap, ModdedPool, Ruleset, Team, Timers, OrderScheme
        from ..core.enums import WinCondition, RefMode
        from ..controllers.bracket import BracketAutoRef
        from ..controllers.qualifiers import QualifiersAutoRef

        match_type = payload.get("type", "bracket")
        room_name  = payload.get("room_name", "autoref match")
        mode       = RefMode(payload.get("mode", "off"))
        best_of    = int(payload.get("best_of", 1))
        bans       = int(payload.get("bans_per_team", 0))
        protects   = int(payload.get("protects_per_team", 0))

        # Build pool from flat map list grouped by mod_group
        # Each entry: {beatmap_id, name, mod_group, mods}
        # mod_group is used to group into ModdedPool; mods is the actual mod string
        map_entries = payload.get("maps", [])
        groups: dict[str, list] = {}
        for e in map_entries:
            g = e.get("mod_group", "NM")
            groups.setdefault(g, []).append(e)

        pool_children = []
        for group_name, entries in groups.items():
            mods_str = entries[0].get("mods", "") if entries else ""
            maps = [PlayableMap(
                int(e["beatmap_id"]),
                name=e.get("name") or f"{group_name}{i+1}",
                is_tiebreaker=e.get("is_tiebreaker", False),
            ) for i, e in enumerate(entries)]
            if mods_str and mods_str.lower() not in ("", "nm", "nomod"):
                if mods_str.lower() == "freemod":
                    pool_children.append(ModdedPool(group_name, "Freemod", *maps))
                else:
                    pool_children.append(ModdedPool(group_name, aiosu.models.mods.Mods(mods_str), *maps))
            else:
                pool_children.append(Pool(group_name, *maps))

        pool = Pool(room_name, *pool_children)

        # Teams
        team_defs = payload.get("teams", [{"name": "Team 1"}, {"name": "Team 2"}])
        teams = []
        for td in team_defs:
            t = Team(td["name"])
            t.players = [type("Player", (), {"username": p})()
                         for p in td.get("players", [])]
            teams.append(t)

        total_players = sum(len(t.players) for t in teams) or int(payload.get("vs", 1))

        ruleset = Ruleset(
            vs=total_players if match_type == "qualifiers" else int(payload.get("vs", 1)),
            gamemode=aiosu.models.Gamemode.STANDARD,
            win_condition=WinCondition.SCORE_V2,
            enforced_mods="NF",
            team_mode=0 if match_type == "qualifiers" else 2,
            best_of=best_of,
            bans_per_team=bans,
            protects_per_team=protects,
            schemes=[OrderScheme("standard", ban_pattern="ABBA")] if match_type == "bracket" else None,
        )

        from ..core.enums import Step
        match = Match(ruleset, pool, lambda _: (0, Step.WIN), *teams)

        client = bancho.BanchoClient(
            username=self._bancho_username,
            password=self._bancho_password,
        )

        iface = WebInterface(match_id=match_id)
        self.register(iface)

        if match_type == "qualifiers":
            ar = QualifiersAutoRef(client=client, match=match,
                                   room_name=room_name, mode=mode)
        else:
            ar = BracketAutoRef(client=client, match=match,
                                room_name=room_name, mode=mode)

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

        task = asyncio.create_task(_run())
        self._tasks[iface.match_id] = task
        return iface

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
            all_matches = (
                [server._pending_summary(mid, p) for mid, p in server._pending.items()] +
                [m.summary() for m in server._matches.values()]
            )
            return JSONResponse(all_matches)

        @app.post("/api/matches")
        async def create_match(request):
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
        async def start_match(match_id: str):
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
