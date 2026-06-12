"""Score editor routes for admins."""
import json
import logging
from typing import TYPE_CHECKING

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from ..server import WebServer

logger = logging.getLogger(__name__)


def register(app: FastAPI, server: "WebServer") -> None:
    from .._auth_dep import require_role

    @app.get("/api/scores/{match_id}")
    async def get_match_scores(match_id: int, user=Depends(require_role("host"))):
        df = server.db.scores.by_match(match_id)
        scores = df.to_dict(orient="records")
        for s in scores:
            if isinstance(s.get("mods"), str):
                try:
                    s["mods"] = json.loads(s["mods"])
                except (json.JSONDecodeError, TypeError):
                    s["mods"] = []
        return JSONResponse({"match_id": match_id, "scores": scores})

    @app.delete("/api/scores/{score_id}")
    async def delete_score(score_id: int, user=Depends(require_role("host"))):
        deleted = server.db.scores.delete_score(score_id)
        if not deleted:
            return JSONResponse({"error": "not_found"}, status_code=404)
        return JSONResponse({"ok": True, "deleted": score_id})

    @app.post("/api/scores")
    async def create_score(request: Request, user=Depends(require_role("host"))):
        try:
            body = await request.json()
            required = ["match_id", "turn", "beatmap_id", "user_id", "score",
                        "accuracy", "max_combo", "passed"]
            for field in required:
                if field not in body:
                    return JSONResponse({"error": f"missing_field_{field}"}, status_code=400)

            score_id = server.db.scores.insert_single_score(
                match_id=int(body["match_id"]),
                turn=int(body["turn"]),
                beatmap_id=int(body["beatmap_id"]),
                user_id=int(body["user_id"]),
                username=body.get("username"),
                team_index=body.get("team_index"),
                score=int(body["score"]),
                accuracy=float(body["accuracy"]),
                max_combo=int(body["max_combo"]),
                mods=body.get("mods", []),
                passed=bool(body["passed"]),
                perfect=bool(body.get("perfect", False)),
                rank=body.get("rank"),
                nmiss=int(body.get("nmiss", 0)),
                n50=int(body.get("n50", 0)),
                n100=int(body.get("n100", 0)),
                n300=int(body.get("n300", 0)),
                ngeki=int(body.get("ngeki", 0)),
                nkatu=int(body.get("nkatu", 0)),
            )
            return JSONResponse({"ok": True, "score_id": score_id}, status_code=201)
        except Exception:
            logger.exception("failed to create score")
            return JSONResponse({"error": "internal_error"}, status_code=500)
