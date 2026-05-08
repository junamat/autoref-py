"""T29: POST /api/matches returns 400 when owner IRC creds missing (V17)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoref.core.auth import new_session
from autoref.core.storage import MatchDatabase
from autoref.web.routes.match import register


@pytest.fixture
def db(tmp_path):
    return MatchDatabase(tmp_path / "test.db")


def _make_app(db):
    app = FastAPI()
    app.state.db = db

    class _FakeServer:
        def __init__(self):
            self.db = db
            self._pending = {}
            self._matches = {}

        def _notify_landing(self):
            pass

        def _pending_summary(self, mid, p):
            return {}

    register(app, _FakeServer())
    return app


def _add_user(db, irc_username=None, irc_password=None, role="host"):
    db._conn.execute(
        "INSERT INTO users(osu_user_id, osu_username, role, irc_username, irc_password, created_at) "
        "VALUES(1, 'testuser', ?, ?, ?, 0)",
        (role, irc_username, irc_password),
    )
    db._conn.commit()
    return db._conn.execute("SELECT id FROM users WHERE osu_user_id = 1").fetchone()[0]


def _cookie(db, user_id):
    return {"session": new_session(user_id, db)}


def test_missing_irc_username_returns_400(db):
    uid = _add_user(db, irc_username=None, irc_password="pw")
    c = TestClient(_make_app(db))
    r = c.post("/api/matches", json={"type": "bracket"}, cookies=_cookie(db, uid))
    assert r.status_code == 400
    body = r.json()
    assert body["error"] == "missing_irc"
    assert body["field"] == "irc_username"


def test_missing_irc_password_returns_400(db):
    uid = _add_user(db, irc_username="myirc", irc_password=None)
    c = TestClient(_make_app(db))
    r = c.post("/api/matches", json={"type": "bracket"}, cookies=_cookie(db, uid))
    assert r.status_code == 400
    body = r.json()
    assert body["error"] == "missing_irc"
    assert body["field"] == "irc_password"


def test_unauthenticated_returns_401(db):
    c = TestClient(_make_app(db))
    r = c.post("/api/matches", json={"type": "bracket"})
    assert r.status_code == 401


def test_valid_creds_creates_pending(db):
    uid = _add_user(db, irc_username="myirc", irc_password="mypw")
    c = TestClient(_make_app(db))
    r = c.post("/api/matches", json={"type": "bracket"}, cookies=_cookie(db, uid))
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending"
    assert "id" in body
