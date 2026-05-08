from typing import TYPE_CHECKING
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

if TYPE_CHECKING:
    from ..server import WebServer


def register(app: FastAPI, server: "WebServer") -> None:
    from ...core.auth import new_session
    from ...core.oauth import authorize_url, exchange_code

    @app.get("/api/auth/login")
    async def login():
        return RedirectResponse(authorize_url(server.config))

    @app.get("/api/auth/callback")
    async def callback(request: Request, code: str):
        try:
            osu_user = await exchange_code(code, server.config)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="OAuth exchange failed") from exc

        count = server.db._conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count == 0:
            params = urlencode({"osu_user_id": osu_user.id, "osu_username": osu_user.username})
            return RedirectResponse(f"/setup?{params}")

        row = server.db._conn.execute(
            "SELECT id FROM users WHERE osu_user_id = ?", (osu_user.id,)
        ).fetchone()
        if row is None:
            return RedirectResponse("/login?error=no_account")

        token = new_session(row[0], server.db)
        response = RedirectResponse("/")
        secure = request.url.scheme == "https"
        response.set_cookie("session", token, httponly=True, samesite="lax", secure=secure)
        return response

    @app.post("/api/auth/logout")
    async def logout(request: Request):
        token = request.cookies.get("session")
        if token:
            server.db._conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            server.db._conn.commit()
        response = JSONResponse({"ok": True})
        response.delete_cookie("session")
        return response
