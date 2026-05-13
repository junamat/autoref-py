import time
from typing import TYPE_CHECKING

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from ..serializers.user import user_row_to_response

if TYPE_CHECKING:
    from ..server import WebServer


def register(app: FastAPI, server: "WebServer") -> None:
    from .._auth_dep import require_login, require_role

    @app.get("/api/users")
    async def list_users(user=Depends(require_role("host"))):
        """List all registered users (host only)."""
        rows = server.db._conn.execute(
            "SELECT id, osu_user_id, osu_username, role, irc_username, created_at FROM users ORDER BY id"
        ).fetchall()
        return JSONResponse([user_row_to_response(r) for r in rows])

    @app.post("/api/users")
    async def create_user(request: Request, user=Depends(require_role("host"))):
        """Create a new user account by osu_username (host only)."""
        body = await request.json()
        osu_username = body.get("osu_username", "").strip()
        if not osu_username:
            raise HTTPException(status_code=400, detail="osu_username required")
        role = body.get("role", "ref")
        if role not in ("host", "ref", "player"):
            raise HTTPException(status_code=400, detail="role must be host, ref, or player")
        now = int(time.time())
        try:
            cursor = server.db._conn.execute(
                "INSERT INTO users(osu_username, role, created_at) VALUES(?, ?, ?)",
                (osu_username, role, now),
            )
            server.db._conn.commit()
        except Exception as exc:
            raise HTTPException(status_code=409, detail="conflict") from exc
        created_row = server.db._conn.execute(
            "SELECT id, osu_user_id, osu_username, role, irc_username, created_at FROM users WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        return JSONResponse(user_row_to_response(created_row), status_code=201)

    @app.patch("/api/users/{uid}")
    async def patch_user(uid: int, request: Request, current=Depends(require_login)):
        """Update a user's IRC credentials or role (self or host only)."""
        if current.role != "host" and current.id != uid:
            raise HTTPException(status_code=403, detail="forbidden")
        body = await request.json()
        _allowed = {"irc_username", "irc_password", "role"}
        updates = {k: v for k, v in body.items() if k in _allowed}
        if not updates:
            return JSONResponse({"ok": True})
        if "role" in updates and current.role != "host":
            raise HTTPException(status_code=403, detail="only host can change role")
        if "role" in updates and updates["role"] not in ("host", "ref", "player"):
            raise HTTPException(status_code=400, detail="role must be host, ref, or player")
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [uid]
        server.db._conn.execute(f"UPDATE users SET {set_clause} WHERE id = ?", vals)
        server.db._conn.commit()
        return JSONResponse({"ok": True})

    @app.delete("/api/users/{uid}")
    async def delete_user(uid: int, user=Depends(require_role("host"))):
        """Delete a user and all their sessions (host only)."""
        server.db._conn.execute("DELETE FROM sessions WHERE user_id = ?", (uid,))
        server.db._conn.execute("DELETE FROM users WHERE id = ?", (uid,))
        server.db._conn.commit()
        return JSONResponse({"ok": True})
