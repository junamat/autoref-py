import time
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
        """Redirect to the osu! OAuth authorization URL."""
        try:
            url = authorize_url(server.config)
        except ValueError:
            raise HTTPException(status_code=400, detail="osu_client_id not configured")
        return RedirectResponse(url)

    @app.get("/api/auth/callback")
    async def callback(request: Request, code: str | None = None, error: str | None = None):
        """Exchange OAuth code, set session cookie, and redirect to landing (or setup)."""
        if error or not code:
            return RedirectResponse(f"/login?error={error or 'missing_code'}")
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
            server.db._conn.execute(
                "INSERT INTO users(osu_user_id, osu_username, role, created_at) VALUES(?, ?, 'player', ?)",
                (osu_user.id, osu_user.username, int(time.time())),
            )
            server.db._conn.commit()
            row = server.db._conn.execute(
                "SELECT id FROM users WHERE osu_user_id = ?", (osu_user.id,)
            ).fetchone()

        token = new_session(row[0], server.db)
        response = RedirectResponse("/")
        secure = request.url.scheme == "https"
        response.set_cookie("session", token, httponly=True, samesite="lax", secure=secure)
        return response

    @app.post("/api/auth/logout")
    async def logout(request: Request):
        """Invalidate the current session cookie."""
        token = request.cookies.get("session")
        if token:
            server.db._conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            server.db._conn.commit()
        response = JSONResponse({"ok": True})
        response.delete_cookie("session")
        return response
