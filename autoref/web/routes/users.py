import time
from typing import TYPE_CHECKING

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from ..server import WebServer


def register(app: FastAPI, server: "WebServer") -> None:
    from .._auth_dep import require_login, require_role

    @app.get("/api/users")
    async def list_users(user=Depends(require_role("host"))):
        rows = server.db._conn.execute(
            "SELECT id, osu_user_id, osu_username, role, irc_username, created_at FROM users ORDER BY id"
        ).fetchall()
        return JSONResponse([{
            "id": r[0], "osu_user_id": r[1], "osu_username": r[2],
            "role": r[3], "irc_username": r[4], "created_at": r[5],
        } for r in rows])

    @app.post("/api/users")
    async def create_user(request: Request, user=Depends(require_role("host"))):
        body = await request.json()
        osu_username = body.get("osu_username", "").strip()
        if not osu_username:
            raise HTTPException(status_code=400, detail="osu_username required")
        role = body.get("role", "ref")
        if role not in ("host", "ref"):
            raise HTTPException(status_code=400, detail="role must be host or ref")
        now = int(time.time())
        try:
            cursor = server.db._conn.execute(
                "INSERT INTO users(osu_username, role, created_at) VALUES(?, ?, ?)",
                (osu_username, role, now),
            )
            server.db._conn.commit()
        except Exception as exc:
            raise HTTPException(status_code=409, detail="conflict") from exc
        return JSONResponse({"id": cursor.lastrowid, "osu_username": osu_username, "role": role}, status_code=201)

    @app.patch("/api/users/{uid}")
    async def patch_user(uid: int, request: Request, current=Depends(require_login)):
        if current.role != "host" and current.id != uid:
            raise HTTPException(status_code=403, detail="forbidden")
        body = await request.json()
        _allowed = {"irc_username", "irc_password", "role"}
        updates = {k: v for k, v in body.items() if k in _allowed}
        if not updates:
            return JSONResponse({"ok": True})
        if "role" in updates and current.role != "host":
            raise HTTPException(status_code=403, detail="only host can change role")
        if "role" in updates and updates["role"] not in ("host", "ref"):
            raise HTTPException(status_code=400, detail="role must be host or ref")
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [uid]
        server.db._conn.execute(f"UPDATE users SET {set_clause} WHERE id = ?", vals)
        server.db._conn.commit()
        return JSONResponse({"ok": True})

    @app.delete("/api/users/{uid}")
    async def delete_user(uid: int, user=Depends(require_role("host"))):
        server.db._conn.execute("DELETE FROM sessions WHERE user_id = ?", (uid,))
        server.db._conn.execute("DELETE FROM users WHERE id = ?", (uid,))
        server.db._conn.commit()
        return JSONResponse({"ok": True})
