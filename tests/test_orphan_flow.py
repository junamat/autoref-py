"""T47: WebServer boot lists orphans; POST/DELETE /api/matches/{id}/resume."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoref.core.auth import new_session
from autoref.core.storage import MatchDatabase
from autoref.web.routes.match import register


@pytest.fixture
def db(tmp_path):
    return MatchDatabase(tmp_path / "test.db")


def _add_user(db, irc_username="myirc", irc_password="mypw", role="host"):
    db._conn.execute(
        "INSERT INTO users(osu_user_id, osu_username, role, irc_username, irc_password, created_at) "
        "VALUES(1, 'testuser', ?, ?, ?, 0)",
        (role, irc_username, irc_password),
    )
    db._conn.commit()
    return db._conn.execute("SELECT id FROM users WHERE osu_user_id = 1").fetchone()[0]


def _cookie(db, user_id):
    return {"session": new_session(user_id, db)}


class _FakeServer:
    def __init__(self, db):
        self.db = db
        self._pending = {}
        self._pending_resume = {}
        self._matches = {}

    def _notify_landing(self):
        pass

    def _pending_summary(self, mid, p):
        return {}


def _make_app(db, fake_server=None):
    app = FastAPI()
    app.state.db = db
    srv = fake_server or _FakeServer(db)
    register(app, srv)
    return app, srv


# ------------------------------------------------------------------ orphan listing

def test_boot_loads_orphans(tmp_path):
    db = MatchDatabase(tmp_path / "test.db")
    db.upsert_live_match("abc123", status="orphaned", controller_type="bracket",
                          payload_json='{"type":"bracket"}')
    db.upsert_live_match("def456", status="running", controller_type="qualifiers",
                          payload_json='{"type":"qualifiers"}')
    db.upsert_live_match("fin789", status="finished")

    orphans = db.get_orphaned_live_matches()
    ids = {r["match_id"] for r in orphans}
    assert "abc123" in ids
    assert "def456" in ids
    assert "fin789" not in ids


# ------------------------------------------------------------------ GET /api/matches includes orphans

def test_api_matches_includes_orphans(db):
    uid = _add_user(db)
    app, srv = _make_app(db)
    srv._pending_resume["orph1"] = {
        "match_id": "orph1", "status": "orphaned", "orphaned": True,
        "payload_json": '{"teams":[{"name":"A"},{"name":"B"}],"best_of":7}',
        "controller_type": "bracket", "bancho_lobby_id": 99, "updated_at": 0,
        "owner_user_id": uid,
    }
    c = TestClient(app)
    r = c.get("/api/matches", cookies=_cookie(db, uid))
    assert r.status_code == 200


# ------------------------------------------------------------------ POST /api/matches/{id}/resume

def test_resume_not_found_returns_404(db):
    uid = _add_user(db)
    app, _ = _make_app(db)
    c = TestClient(app)
    r = c.post("/api/matches/nonexistent/resume", cookies=_cookie(db, uid))
    assert r.status_code == 404


def test_resume_unauthenticated_returns_401(db):
    _add_user(db)
    app, _ = _make_app(db)
    c = TestClient(app)
    r = c.post("/api/matches/some/resume")
    assert r.status_code == 401


# ------------------------------------------------------------------ DELETE /api/matches/{id}/resume

def test_discard_orphan_marks_crashed(db):
    uid = _add_user(db)
    db.upsert_live_match("orph1", status="orphaned", owner_user_id=uid,
                          payload_json='{}')
    app, srv = _make_app(db)
    srv._pending_resume["orph1"] = {
        "match_id": "orph1", "status": "orphaned", "owner_user_id": uid,
        "payload_json": "{}", "bancho_lobby_id": None,
    }
    c = TestClient(app)
    r = c.delete("/api/matches/orph1/resume", cookies=_cookie(db, uid))
    assert r.status_code == 200
    assert r.json()["ok"] is True
    # row should now be 'crashed' in DB
    row = db._conn.execute(
        "SELECT status FROM live_matches WHERE match_id = 'orph1'"
    ).fetchone()
    assert row[0] == "crashed"
    # removed from pending_resume
    assert "orph1" not in srv._pending_resume


def test_discard_orphan_forbidden_for_wrong_user(db):
    uid1 = _add_user(db)
    # add second user
    db._conn.execute(
        "INSERT INTO users(osu_user_id, osu_username, role, created_at) VALUES(2, 'other', 'ref', 0)"
    )
    db._conn.commit()
    uid2 = db._conn.execute("SELECT id FROM users WHERE osu_user_id = 2").fetchone()[0]

    db.upsert_live_match("orph2", status="orphaned", owner_user_id=uid1, payload_json="{}")
    app, srv = _make_app(db)
    srv._pending_resume["orph2"] = {
        "match_id": "orph2", "status": "orphaned", "owner_user_id": uid1,
        "payload_json": "{}",
    }
    c = TestClient(app)
    r = c.delete("/api/matches/orph2/resume", cookies=_cookie(db, uid2))
    assert r.status_code == 403


def test_discard_not_found_returns_404(db):
    uid = _add_user(db)
    app, _ = _make_app(db)
    c = TestClient(app)
    r = c.delete("/api/matches/ghost/resume", cookies=_cookie(db, uid))
    assert r.status_code == 404
