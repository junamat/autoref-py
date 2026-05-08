"""T28: role gating — host-only routes, self-edit, ref restrictions."""
import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from autoref.core.auth import new_session
from autoref.core.storage import MatchDatabase
from autoref.web._auth_dep import require_login, require_role


@pytest.fixture
def db(tmp_path):
    return MatchDatabase(tmp_path / "test.db")


def _make_app(db):
    app = FastAPI()
    app.state.db = db

    @app.get("/host-only")
    async def host_only(user=Depends(require_role("host"))):
        return {"role": user.role}

    @app.get("/me")
    async def me(user=Depends(require_login)):
        return {"id": user.id, "role": user.role}

    return app


def _add_user(db, osu_user_id, role):
    db._conn.execute(
        "INSERT INTO users(osu_user_id, osu_username, role, created_at) VALUES(?, ?, ?, 0)",
        (osu_user_id, f"user{osu_user_id}", role),
    )
    db._conn.commit()
    return db._conn.execute("SELECT id FROM users WHERE osu_user_id = ?", (osu_user_id,)).fetchone()[0]


def _session_cookie(db, user_id):
    token = new_session(user_id, db)
    return {"session": token}


# V15: host-only route returns 200 for host, 403 for ref
def test_host_only_allows_host(db):
    uid = _add_user(db, 1, "host")
    c = TestClient(_make_app(db))
    r = c.get("/host-only", cookies=_session_cookie(db, uid))
    assert r.status_code == 200
    assert r.json()["role"] == "host"


def test_host_only_rejects_ref(db):
    uid = _add_user(db, 2, "ref")
    c = TestClient(_make_app(db))
    r = c.get("/host-only", cookies=_session_cookie(db, uid))
    assert r.status_code == 403


def test_require_login_rejects_unauthenticated(db):
    c = TestClient(_make_app(db))
    r = c.get("/me")
    assert r.status_code == 401


# V16: PATCH /api/users/{id} — host can edit anyone, ref can only edit self
def _users_app(db):
    from autoref.web.routes.users import register
    app = FastAPI()
    app.state.db = db

    class _FakeServer:
        def __init__(self):
            self.db = db

    register(app, _FakeServer())
    return app


def test_patch_self_allowed_for_ref(db):
    uid = _add_user(db, 3, "ref")
    c = TestClient(_users_app(db))
    r = c.patch(f"/api/users/{uid}", json={"irc_username": "myirc"}, cookies=_session_cookie(db, uid))
    assert r.status_code == 200


def test_patch_other_forbidden_for_ref(db):
    uid1 = _add_user(db, 4, "ref")
    uid2 = _add_user(db, 5, "ref")
    c = TestClient(_users_app(db))
    r = c.patch(f"/api/users/{uid2}", json={"irc_username": "x"}, cookies=_session_cookie(db, uid1))
    assert r.status_code == 403


def test_host_can_patch_any(db):
    host_id = _add_user(db, 6, "host")
    ref_id = _add_user(db, 7, "ref")
    c = TestClient(_users_app(db))
    r = c.patch(f"/api/users/{ref_id}", json={"irc_username": "irc7"}, cookies=_session_cookie(db, host_id))
    assert r.status_code == 200


def test_ref_cannot_change_role(db):
    uid = _add_user(db, 8, "ref")
    c = TestClient(_users_app(db))
    r = c.patch(f"/api/users/{uid}", json={"role": "host"}, cookies=_session_cookie(db, uid))
    assert r.status_code == 403
