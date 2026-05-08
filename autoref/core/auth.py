import base64
import secrets
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request
    from .storage import MatchDatabase

SESSION_LIFETIME = 30 * 24 * 3600


@dataclass
class User:
    id: int
    osu_user_id: int | None
    osu_username: str
    role: str
    irc_username: str | None
    irc_password: str | None


def new_session(user_id: int, db: "MatchDatabase") -> str:
    token = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    expires_at = int(time.time()) + SESSION_LIFETIME
    db._conn.execute(
        "INSERT INTO sessions(token, user_id, expires_at) VALUES(?, ?, ?)",
        (token, user_id, expires_at),
    )
    db._conn.commit()
    return token


def current_user(request: "Request", db: "MatchDatabase") -> "User | None":
    token = request.cookies.get("session")
    if not token:
        return None
    now = int(time.time())
    row = db._conn.execute(
        """
        SELECT u.id, u.osu_user_id, u.osu_username, u.role, u.irc_username, u.irc_password
        FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token = ? AND s.expires_at > ?
        """,
        (token, now),
    ).fetchone()
    if row is None:
        return None
    return User(
        id=row[0], osu_user_id=row[1], osu_username=row[2],
        role=row[3], irc_username=row[4], irc_password=row[5],
    )
