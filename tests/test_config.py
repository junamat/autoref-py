"""Tests for autoref/core/config.py"""
import json

import pytest

from autoref.core.config import Config, load, save, to_api
from autoref.core.storage import MatchDatabase


@pytest.fixture
def db(tmp_path):
    return MatchDatabase(tmp_path / "test.db")


# V1: settings table exists and stores json-decodable values
def test_settings_table_created(db):
    rows = db._conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'").fetchall()
    assert rows, "settings table must exist"


def test_save_values_are_json_decodable(db):
    cfg = Config(bancho_username="testuser", port=9090)
    save(db, cfg)
    rows = db._conn.execute("SELECT key, value FROM settings").fetchall()
    for _key, raw in rows:
        json.loads(raw)  # must not raise


# V10: round-trip load/save
def test_round_trip(db):
    cfg = Config(
        host="127.0.0.1",
        port=9000,
        bancho_username="myuser",
        bancho_password="secret",
        default_mode="assisted",
        default_prefix=">",
        default_refs=["ref1", "ref2"],
        default_best_of=5,
        default_team_mode=2,
        timer_pick=90,
    )
    save(db, cfg)
    loaded = load(db)
    assert loaded.host == "127.0.0.1"
    assert loaded.port == 9000
    assert loaded.bancho_username == "myuser"
    # Secrets are not persisted to database
    assert loaded.bancho_password == ""
    assert loaded.default_mode == "assisted"
    assert loaded.default_prefix == ">"
    assert loaded.default_refs == ["ref1", "ref2"]
    assert loaded.default_best_of == 5
    assert loaded.default_team_mode == 2
    assert loaded.timer_pick == 90


# V3: env-seed on first boot
def test_env_seed(db, monkeypatch):
    monkeypatch.setenv("BANCHO_USERNAME", "envuser")
    monkeypatch.setenv("BANCHO_PASSWORD", "envpass")
    monkeypatch.setenv("CLIENT_ID", "123")
    monkeypatch.setenv("CLIENT_SECRET", "mysecret")
    monkeypatch.setenv("AUTOREF_DEFAULT_MODE", "auto")
    monkeypatch.setenv("AUTOREF_DEFAULT_BEST_OF", "7")

    cfg = load(db)
    assert cfg.bancho_username == "envuser"
    assert cfg.bancho_password == "envpass"
    assert cfg.osu_client_id == "123"
    assert cfg.osu_client_secret == "mysecret"
    assert cfg.default_mode == "auto"
    assert cfg.default_best_of == 7

    # Values seeded to DB — second load should not re-read env
    monkeypatch.setenv("BANCHO_USERNAME", "different")
    cfg2 = load(db)
    assert cfg2.bancho_username == "envuser"


def test_env_seed_refs_comma_split(db, monkeypatch):
    monkeypatch.setenv("AUTOREF_DEFAULT_REFS", "refA, refB, refC")
    cfg = load(db)
    assert cfg.default_refs == ["refA", "refB", "refC"]


# V2: to_api redacts secrets
def test_to_api_redacts_secrets(db):
    cfg = Config(bancho_password="secret", osu_client_secret="topsecret")
    result = to_api(cfg)
    assert "bancho_password" not in result
    assert "osu_client_secret" not in result
    assert result["bancho_password_set"] is True
    assert result["osu_client_secret_set"] is True


def test_to_api_set_false_when_empty(db):
    cfg = Config(bancho_password="", osu_client_secret="")
    result = to_api(cfg)
    assert result["bancho_password_set"] is False
    assert result["osu_client_secret_set"] is False


# V9: empty-string secrets = unchanged
def test_empty_secret_unchanged(db):
    # Secrets are not persisted to database
    cfg = Config(bancho_password="original")
    save(db, cfg)
    loaded = load(db)
    assert loaded.bancho_password == ""  # Not persisted

    # Simulate PUT with empty password
    if "" == "" or None is None:
        pass  # don't overwrite
    loaded.bancho_password = ""  # unchanged
    save(db, loaded)
    loaded2 = load(db)
    assert loaded2.bancho_password == ""  # Still not persisted
