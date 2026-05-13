"""Match template CRUD routes."""
import json
import time
from typing import TYPE_CHECKING

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from ..server import WebServer


def register(app: FastAPI, server: "WebServer") -> None:
    from .._auth_dep import require_not_player

    def _row_to_dict(row) -> dict:
        return {
            "id": row[0],
            "name": row[1],
            "payload": json.loads(row[2]),
            "created_by": row[3],
            "created_at": row[4],
        }

    @app.get("/api/match-templates")
    async def list_templates(_user=Depends(require_not_player)):
        rows = server.db._conn.execute(
            "SELECT id, name, payload_json, created_by, created_at FROM match_templates ORDER BY name"
        ).fetchall()
        return JSONResponse([_row_to_dict(r) for r in rows])

    @app.get("/api/match-templates/{template_id}")
    async def get_template(template_id: int, _user=Depends(require_not_player)):
        row = server.db._conn.execute(
            "SELECT id, name, payload_json, created_by, created_at FROM match_templates WHERE id = ?",
            (template_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="not found")
        return JSONResponse(_row_to_dict(row))

    @app.post("/api/match-templates")
    async def create_template(request: Request, user=Depends(require_not_player)):
        body = await request.json()
        name = (body.get("name") or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="name required")
        payload = body.get("payload")
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="payload required")
        now = int(time.time())
        try:
            cursor = server.db._conn.execute(
                "INSERT INTO match_templates(name, payload_json, created_by, created_at) VALUES(?, ?, ?, ?)",
                (name, json.dumps(payload), user.id, now),
            )
            server.db._conn.commit()
        except Exception as exc:
            if "UNIQUE" in str(exc).upper():
                raise HTTPException(status_code=409, detail="template name already exists") from exc
            raise HTTPException(status_code=500, detail="internal_error") from exc
        row = server.db._conn.execute(
            "SELECT id, name, payload_json, created_by, created_at FROM match_templates WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        return JSONResponse(_row_to_dict(row), status_code=201)

    @app.delete("/api/match-templates/{template_id}")
    async def delete_template(template_id: int, _user=Depends(require_not_player)):
        cur = server.db._conn.execute(
            "DELETE FROM match_templates WHERE id = ?", (template_id,)
        )
        server.db._conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="not found")
        return JSONResponse({"ok": True})
