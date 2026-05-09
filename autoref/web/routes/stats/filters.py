from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from ._common import _POOL_STORE

if TYPE_CHECKING:
    from ...server import WebServer


def register(app: FastAPI, server: "WebServer") -> None:
    @app.get("/api/stats/filters")
    async def api_stats_filters():
        """Available pool / round combinations for the /stats filter UI.
        Pool ids are joined with their human-readable names from PoolStore.
        """
        from ....core.stats import METHODS
        opts = server.db.get_filter_options()
        pools_full = {p["id"]: p for p in _POOL_STORE.list()}
        pool_defaults = {
            pid: (pools_full.get(pid, {}).get("stats_defaults") or {})
            for pid in opts["pools"]
        }
        return JSONResponse({
            "pools":  [{"id": pid, "name": pools_full.get(pid, {}).get("name", pid)} for pid in opts["pools"]],
            "rounds": opts["rounds"],
            "combos": opts["combos"],
            "pool_defaults": pool_defaults,
            "methods": [{"key": k, "label": v[0]} for k, v in METHODS.items()],
        })
