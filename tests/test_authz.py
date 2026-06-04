"""T28/T108: role gating — host-only routes, self-edit, ref/player restrictions."""
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from autoref.core.auth import new_session
from autoref.core.storage import MatchDatabase
from autoref.web._auth_dep import require_login, require_not_player, require_role


@pytest.fixture
def db(tmp_path):
    return MatchDatabase(tmp_path / "test.db")


def _make_app(db):
    app = FastAPI()
    app.state.db = db

    @app.get("/host-only")
    async def host_only(user=Depends(require_role("host"))):
        return {"role": user.role}

    @app.get("/not-player")
    async def not_player(user=Depends(require_not_player)):
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


# V15b: require_not_player — allows host/ref, rejects player
def test_not_player_allows_ref(db):
    uid = _add_user(db, 10, "ref")
    c = TestClient(_make_app(db))
    r = c.get("/not-player", cookies=_session_cookie(db, uid))
    assert r.status_code == 200


def test_not_player_allows_host(db):
    uid = _add_user(db, 11, "host")
    c = TestClient(_make_app(db))
    r = c.get("/not-player", cookies=_session_cookie(db, uid))
    assert r.status_code == 200


def test_not_player_rejects_player(db):
    uid = _add_user(db, 12, "player")
    c = TestClient(_make_app(db))
    r = c.get("/not-player", cookies=_session_cookie(db, uid))
    assert r.status_code == 403


def test_not_player_rejects_unauthenticated(db):
    c = TestClient(_make_app(db))
    r = c.get("/not-player")
    assert r.status_code == 401


# V15c: page redirects — player gets 302 to /stats
def _pages_app(db, server_static_dir):
    from pathlib import Path

    from fastapi.responses import FileResponse

    from autoref.web.routes.pages import register

    class _FakeServer:
        def __init__(self):
            self.db = db
            self.static_dir = Path(server_static_dir)

    app = FastAPI()
    app.state.db = db
    register(app, _FakeServer())
    return app


def test_index_public_for_player(db, tmp_path):
    (tmp_path / "stats.html").write_text("<html/>")
    uid = _add_user(db, 20, "player")
    c = TestClient(_pages_app(db, tmp_path), follow_redirects=False)
    r = c.get("/", cookies=_session_cookie(db, uid))
    assert r.status_code == 200


def test_index_public_for_anon(db, tmp_path):
    (tmp_path / "stats.html").write_text("<html/>")
    c = TestClient(_pages_app(db, tmp_path), follow_redirects=False)
    r = c.get("/")
    assert r.status_code == 200


def test_ref_redirects_player(db, tmp_path):
    (tmp_path / "ref.html").write_text("<html/>")
    uid = _add_user(db, 24, "player")
    c = TestClient(_pages_app(db, tmp_path), follow_redirects=False)
    r = c.get("/ref", cookies=_session_cookie(db, uid))
    assert r.status_code == 302
    assert r.headers["location"] == "/"


def test_ref_redirects_anon(db, tmp_path):
    (tmp_path / "ref.html").write_text("<html/>")
    c = TestClient(_pages_app(db, tmp_path), follow_redirects=False)
    r = c.get("/ref")
    assert r.status_code == 302
    assert r.headers["location"] == "/"


def test_ref_allows_ref(db, tmp_path):
    (tmp_path / "ref.html").write_text("<html/>")
    uid = _add_user(db, 21, "ref")
    c = TestClient(_pages_app(db, tmp_path), follow_redirects=False)
    r = c.get("/ref", cookies=_session_cookie(db, uid))
    assert r.status_code == 200


def test_pool_builder_redirects_player(db, tmp_path):
    (tmp_path / "pool_builder.html").write_text("<html/>")
    uid = _add_user(db, 22, "player")
    c = TestClient(_pages_app(db, tmp_path), follow_redirects=False)
    r = c.get("/pool-builder", cookies=_session_cookie(db, uid))
    assert r.status_code == 302
    assert r.headers["location"] == "/"


def test_pool_builder_redirects_anon(db, tmp_path):
    (tmp_path / "pool_builder.html").write_text("<html/>")
    c = TestClient(_pages_app(db, tmp_path), follow_redirects=False)
    r = c.get("/pool-builder")
    assert r.status_code == 302
    assert r.headers["location"] == "/"


def test_settings_redirects_player(db, tmp_path):
    (tmp_path / "settings.html").write_text("<html/>")
    uid = _add_user(db, 23, "player")
    c = TestClient(_pages_app(db, tmp_path), follow_redirects=False)
    r = c.get("/settings", cookies=_session_cookie(db, uid))
    assert r.status_code == 302
    assert r.headers["location"] == "/"


def test_settings_redirects_anon(db, tmp_path):
    (tmp_path / "settings.html").write_text("<html/>")
    c = TestClient(_pages_app(db, tmp_path), follow_redirects=False)
    r = c.get("/settings")
    assert r.status_code == 302
    assert r.headers["location"] == "/"
