from typing import TYPE_CHECKING

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from ..server import WebServer


def register(app: FastAPI, server: "WebServer") -> None:
    from .._auth_dep import require_login

    @app.get("/api/account")
    async def get_account(user=Depends(require_login)):
        return JSONResponse({
            "id": user.id,
            "osu_user_id": user.osu_user_id,
            "osu_username": user.osu_username,
            "role": user.role,
            "irc_username": user.irc_username,
            "irc_set": bool(user.irc_username and user.irc_password),
        })

    @app.put("/api/account")
    async def put_account(request: Request, user=Depends(require_login)):
        body = await request.json()
        irc_username = body.get("irc_username")
        irc_password = body.get("irc_password")
        if irc_username is not None:
            server.db._conn.execute(
                "UPDATE users SET irc_username = ? WHERE id = ?", (irc_username, user.id)
            )
        if irc_password:
            server.db._conn.execute(
                "UPDATE users SET irc_password = ? WHERE id = ?", (irc_password, user.id)
            )
        server.db._conn.commit()
        return JSONResponse({"ok": True})
