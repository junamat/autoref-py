"""Tests for GET/PUT /api/settings"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoref.core.config import Config
from autoref.core.config import load as load_config
from autoref.core.config import save as save_config
from autoref.core.storage import MatchDatabase
from autoref.web.routes.settings import register


def make_app(db, cfg=None):
    app = FastAPI()

    class FakeServer:
        def __init__(self):
            self.db = db
            self.config = cfg or load_config(db)
            self.host = self.config.host
            self.port = self.config.port

    register(app, FakeServer())
    return app


@pytest.fixture
def db(tmp_path):
    return MatchDatabase(tmp_path / "test.db")


@pytest.fixture
def client(db):
    return TestClient(make_app(db))


# V2: GET shape — no secrets, *_set flags present
def test_get_settings_no_secrets(db):
    cfg = Config(bancho_password="pw", osu_client_secret="sec")
    save_config(db, cfg)
    app = make_app(db, cfg)
    c = TestClient(app)
    r = c.get("/api/settings")
    assert r.status_code == 200
    body = r.json()
    assert "bancho_password" not in body
    assert "osu_client_secret" not in body
    assert body["bancho_password_set"] is True
    assert body["osu_client_secret_set"] is True


def test_get_settings_set_false_when_empty(db):
    cfg = Config(bancho_password="", osu_client_secret="")
    save_config(db, cfg)
    app = make_app(db, cfg)
    c = TestClient(app)
    body = c.get("/api/settings").json()
    assert body["bancho_password_set"] is False
    assert body["osu_client_secret_set"] is False


# V4: PUT validates fields
@pytest.mark.parametrize("payload,fragment", [
    ({"port": 0},                   "port"),
    ({"port": 99999},               "port"),
    ({"port": "abc"},               "port"),
    ({"default_mode": "super"},     "default_mode"),
    ({"default_prefix": "ab"},      "default_prefix"),
    ({"default_prefix": ""},        "default_prefix"),
    ({"default_refs": "notalist"},  "default_refs"),
    ({"default_best_of": 0},        "default_best_of"),
    ({"default_team_mode": 1},      "default_team_mode"),
    ({"timer_pick": -1},            "timer_pick"),
])
def test_put_validates(client, payload, fragment):
    r = client.put("/api/settings", json=payload)
    assert r.status_code == 400
    text = str(r.json())
    assert fragment in text


def test_put_valid(client):
    r = client.put("/api/settings", json={"port": 9000, "default_mode": "auto"})
    assert r.status_code == 200
    assert "requires_restart" in r.json()


# V5: requires_restart
def test_requires_restart_on_port_change(db):
    cfg = Config(port=8080)
    save_config(db, cfg)
    app = make_app(db, cfg)
    c = TestClient(app)
    r = c.put("/api/settings", json={"port": 9999})
    assert r.json()["requires_restart"] is True


def test_no_restart_for_other_fields(db):
    cfg = Config(port=8080)
    save_config(db, cfg)
    app = make_app(db, cfg)
    c = TestClient(app)
    r = c.put("/api/settings", json={"default_mode": "auto"})
    assert r.json()["requires_restart"] is False


# V9: empty-string secret = unchanged
def test_empty_secret_not_overwritten(db):
    cfg = Config(bancho_password="original")
    save_config(db, cfg)
    app = make_app(db, cfg)
    c = TestClient(app)
    c.put("/api/settings", json={"bancho_password": ""})
    reloaded = load_config(db)
    assert reloaded.bancho_password == "original"


def test_nonempty_secret_overwritten(db):
    cfg = Config(bancho_password="old")
    save_config(db, cfg)
    app = make_app(db, cfg)
    c = TestClient(app)
    c.put("/api/settings", json={"bancho_password": "new"})
    reloaded = load_config(db)
    assert reloaded.bancho_password == "new"


# persistence
def test_put_persists_to_db(db):
    cfg = Config()
    save_config(db, cfg)
    app = make_app(db, cfg)
    c = TestClient(app)
    c.put("/api/settings", json={"bancho_username": "saveduser"})
    reloaded = load_config(db)
    assert reloaded.bancho_username == "saveduser"
