"""Pool CRUD + beatmap metadata routes."""
import logging
from typing import TYPE_CHECKING

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from ...core.beatmap_cache import get_beatmap_cache
from ...core.result import Err
from .._state import _POOL_STORE
from ..serializers.beatmap import beatmap_to_response
from ..serializers.pool import pool_to_detail

if TYPE_CHECKING:
    from ..server import WebServer

logger = logging.getLogger(__name__)


def register(app: FastAPI, server: "WebServer") -> None:
    from .._auth_dep import require_not_player

    @app.get("/api/pools")
    async def list_pools():
        return JSONResponse([pool_to_detail(p) for p in _POOL_STORE.list()])

    @app.post("/api/pools")
    async def save_pool(request: Request, _user=Depends(require_not_player)):
        try:
            body = await request.json()
            pool_id = _POOL_STORE.save(body)
            return JSONResponse({"id": pool_id}, status_code=201)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        except Exception:
            logger.exception("failed to save pool")
            return JSONResponse({"error": "internal_error"}, status_code=500)

    @app.delete("/api/pools/{pool_id}")
    async def delete_pool(pool_id: str, _user=Depends(require_not_player)):
        if not _POOL_STORE.delete(pool_id):
            return JSONResponse({"error": "not found"}, status_code=404)
        return JSONResponse({"ok": True})

    @app.get("/api/beatmap/{beatmap_id}")
    async def get_beatmap(beatmap_id: str):
        """Fetch beatmap metadata from osu! API (cache-backed)."""
        result = await get_beatmap_cache().fetch_one(int(beatmap_id))
        if isinstance(result, Err):
            return JSONResponse({"error": result.reason}, status_code=404)
        return JSONResponse(beatmap_to_response(result.value))

    @app.get("/api/beatmap/{beatmap_id}/attributes")
    async def get_beatmap_attributes(beatmap_id: str, mods: str = ""):
        """Fetch beatmap difficulty attributes with mods from osu! API."""
        from aiosu.models import Mods

        from ...client import make_client
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
        except Exception:
            logger.exception("failed to fetch beatmap attributes %s mods=%s", beatmap_id, mods)
            return JSONResponse({"error": "internal_error"}, status_code=500)
        finally:
            await client.aclose()
