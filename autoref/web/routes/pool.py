"""Pool CRUD + beatmap metadata routes."""
import logging
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .._state import _POOL_STORE
from ...core.beatmap_cache import get_beatmap_cache

if TYPE_CHECKING:
    from ..server import WebServer

logger = logging.getLogger(__name__)


def register(app: FastAPI, server: "WebServer") -> None:
    @app.get("/api/pools")
    async def list_pools():
        return JSONResponse(_POOL_STORE.list())

    @app.post("/api/pools")
    async def save_pool(request: Request):
        try:
            body = await request.json()
            pool_id = _POOL_STORE.save(body)
            return JSONResponse({"id": pool_id}, status_code=201)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    @app.delete("/api/pools/{pool_id}")
    async def delete_pool(pool_id: str):
        if not _POOL_STORE.delete(pool_id):
            return JSONResponse({"error": "not found"}, status_code=404)
        return JSONResponse({"ok": True})

    @app.get("/api/beatmap/{beatmap_id}")
    async def get_beatmap(beatmap_id: str):
        """Fetch beatmap metadata from osu! API (cache-backed)."""
        try:
            meta = await get_beatmap_cache().fetch_one(int(beatmap_id))
        except Exception as e:
            logger.exception(f"failed to fetch beatmap {beatmap_id}")
            return JSONResponse({"error": str(e)}, status_code=500)
        if meta is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        # API response shape kept stable: web UI consumes `len`/`diff`.
        return JSONResponse({
            "id":            meta.get("id"),
            "beatmapset_id": meta.get("beatmapset_id"),
            "title":         meta.get("title", ""),
            "artist":        meta.get("artist", ""),
            "diff":          meta.get("version", ""),
            "len":           meta.get("total_length", 0),
            "stars":         meta.get("stars", 0.0),
            "ar":            meta.get("ar", 0.0),
            "od":            meta.get("od", 0.0),
            "cs":            meta.get("cs", 0.0),
            "hp":            meta.get("hp", 0.0),
        })

    @app.get("/api/beatmap/{beatmap_id}/attributes")
    async def get_beatmap_attributes(beatmap_id: str, mods: str = ""):
        """Fetch beatmap difficulty attributes with mods from osu! API."""
        from ...client import make_client
        from aiosu.models import Mods
        client = make_client()
        try:
            mods_obj = Mods(mods) if mods else None
            attrs = await client.get_beatmap_attributes(int(beatmap_id), mods=mods_obj)
            return JSONResponse({
                "star_rating": round(attrs.star_rating, 2),
                "max_combo": attrs.max_combo,
                "ar": round(attrs.approach_rate, 1) if attrs.approach_rate else None,
                "od": round(attrs.overall_difficulty, 1) if attrs.overall_difficulty else None,
            })
        except Exception as e:
            logger.exception(f"failed to fetch beatmap attributes {beatmap_id} with mods {mods}")
            return JSONResponse({"error": str(e)}, status_code=500)
        finally:
            await client.aclose()
