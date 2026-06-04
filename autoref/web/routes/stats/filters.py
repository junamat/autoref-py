from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from ._common import _POOL_STORE

if TYPE_CHECKING:
    from ...server import WebServer


def _extract_colors(tree: list[dict], parent_color: str | None = None) -> dict[str, str]:
    """Walk pool tree and extract {beatmap_id: color} for any node with a color set."""
    colors: dict[str, str] = {}
    for node in tree:
        color = node.get("color") or parent_color
        if node.get("type") == "map":
            bid = node.get("bid")
            if bid and color:
                colors[str(bid)] = color
        children = node.get("children")
        if children:
            colors.update(_extract_colors(children, color))
    return colors


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
        # Return ALL pools from store, not just those with matches
        all_pools = [
            {"id": pid, "name": pools_full.get(pid, {}).get("name", pid)}
            for pid in pools_full.keys()
        ]
        # Extract custom colors for each pool
        pool_colors = {}
        for pid, pdata in pools_full.items():
            tree = pdata.get("tree", [])
            colors = _extract_colors(tree)
            if colors:
                pool_colors[pid] = colors
        return JSONResponse({
            "pools":  all_pools,
            "rounds": opts["rounds"],
            "combos": opts["combos"],
            "pool_defaults": pool_defaults,
            "pool_colors": pool_colors,
            "methods": [{"key": k, "label": v[0]} for k, v in METHODS.items()],
        })
