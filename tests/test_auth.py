"""T27: session lifecycle, current_user, gate middleware."""
import time
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoref.core.auth import User, current_user, new_session
from autoref.core.storage import MatchDatabase
from autoref.web._gate import SetupGateMiddleware


@pytest.fixture
def db(tmp_path):
    return MatchDatabase(tmp_path / "test.db")


def _insert_user(db, osu_user_id=100, osu_username="testuser", role="host"):
    db._conn.execute(
        "INSERT INTO users(osu_user_id, osu_username, role, created_at) VALUES(?, ?, ?, 0)",
        (osu_user_id, osu_username, role),
    )
    db._conn.commit()
    return db._conn.execute("SELECT id FROM users WHERE osu_user_id = ?", (osu_user_id,)).fetchone()[0]


# V12: token = 32 bytes b64url, lifetime 30 days
def test_new_session_token_format(db):
    uid = _insert_user(db)
    token = new_session(uid, db)
    assert len(token) > 20
    assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in token)


def test_new_session_expires_in_30_days(db):
    uid = _insert_user(db)
    before = int(time.time())
    new_session(uid, db)
    row = db._conn.execute("SELECT expires_at FROM sessions ORDER BY rowid DESC LIMIT 1").fetchone()
    assert row[0] >= before + 30 * 24 * 3600 - 5


# V20: current_user validates session
def test_current_user_valid(db):
    uid = _insert_user(db)
    token = new_session(uid, db)
    req = MagicMock()
    req.cookies = {"session": token}
    user = current_user(req, db)
    assert user is not None
    assert user.osu_username == "testuser"
    assert user.role == "host"


def test_current_user_no_cookie(db):
    req = MagicMock()
    req.cookies = {}
    assert current_user(req, db) is None


def test_current_user_invalid_token(db):
    req = MagicMock()
    req.cookies = {"session": "bogus"}
    assert current_user(req, db) is None


def test_current_user_expired(db):
    uid = _insert_user(db)
    past = int(time.time()) - 1
    db._conn.execute(
        "INSERT INTO sessions(token, user_id, expires_at) VALUES('exp', ?, ?)", (uid, past)
    )
    db._conn.commit()
    req = MagicMock()
    req.cookies = {"session": "exp"}
    assert current_user(req, db) is None


# V13: gate middleware returns 503 when users table empty
def _gate_app(db):
    app = FastAPI()
    app.state.db = db

    @app.get("/api/matches")
    async def matches():
        return {"ok": True}

    @app.get("/api/auth/login")
    async def login():
        return {"ok": True}

    @app.get("/setup")
    async def setup_page():
        return {"ok": True}

    app.add_middleware(SetupGateMiddleware, db=db)
    return app


def test_gate_blocks_when_no_users(db):
    c = TestClient(_gate_app(db), raise_server_exceptions=False)
    r = c.get("/api/matches")
    assert r.status_code == 503
    assert r.json()["error"] == "setup_required"


def test_gate_allows_login_route(db):
    c = TestClient(_gate_app(db), raise_server_exceptions=False)
    r = c.get("/api/auth/login")
    assert r.status_code == 200


def test_gate_allows_setup_page(db):
    c = TestClient(_gate_app(db), raise_server_exceptions=False)
    r = c.get("/setup")
    assert r.status_code == 200


def test_gate_passes_when_users_exist(db):
    _insert_user(db)
    c = TestClient(_gate_app(db), raise_server_exceptions=False)
    r = c.get("/api/matches")
    assert r.status_code == 200
