import time
from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from ..server import WebServer


def register(app: FastAPI, server: "WebServer") -> None:
    from ...core.auth import new_session

    @app.post("/api/setup")
    async def setup(request: Request):
        count = server.db._conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count > 0:
            raise HTTPException(status_code=403, detail="already set up")

        body = await request.json()
        osu_user_id = body.get("osu_user_id")
        osu_username = body.get("osu_username", "").strip()
        if not osu_user_id or not osu_username:
            raise HTTPException(status_code=400, detail="missing osu_user_id or osu_username")

        now = int(time.time())
        cursor = server.db._conn.execute(
            "INSERT INTO users(osu_user_id, osu_username, role, created_at) VALUES(?, ?, 'host', ?)",
            (int(osu_user_id), osu_username, now),
        )
        user_id = cursor.lastrowid
        assert user_id is not None
        server.db._conn.commit()

        token = new_session(user_id, server.db)
        response = JSONResponse({"ok": True, "user_id": user_id})
        secure = request.url.scheme == "https"
        response.set_cookie("session", token, httponly=True, samesite="lax", secure=secure)
        return response
