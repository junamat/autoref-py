"""Unit tests for web serializer pure functions (V50 — no HTTP, no DB)."""
import json
from unittest.mock import MagicMock

import pandas as pd
import pytest

from autoref.core.auth import User
from autoref.web.serializers.beatmap import beatmap_to_response
from autoref.web.serializers.match import active_to_summary, orphan_to_summary, pending_to_summary
from autoref.web.serializers.pool import pool_to_detail, pool_to_summary
from autoref.web.serializers.stats import build_mappool_row, enrich_leaderboard_rows
from autoref.web.serializers.user import user_row_to_response, user_to_account_response

# ── beatmap ──────────────────────────────────────────────────────────────────

def test_beatmap_to_response_maps_fields():
    meta = {
        "id": 123, "beatmapset_id": 456, "title": "Song", "artist": "Artist",
        "version": "Hard", "total_length": 180, "stars": 5.5,
        "ar": 9.0, "od": 8.5, "cs": 4.0, "hp": 6.0,
    }
    r = beatmap_to_response(meta)
    assert r["id"] == 123
    assert r["diff"] == "Hard"
    assert r["len"] == 180
    assert r["stars"] == 5.5


def test_beatmap_to_response_missing_fields():
    r = beatmap_to_response({})
    assert r["title"] == ""
    assert r["len"] == 0
    assert r["stars"] == 0.0


# ── pool ─────────────────────────────────────────────────────────────────────

def test_pool_to_summary_extracts_id_name():
    pool = {"id": "nm", "name": "NM Pool", "tree": [{"type": "map"}]}
    s = pool_to_summary(pool)
    assert s == {"id": "nm", "name": "NM Pool"}
    assert "tree" not in s


def test_pool_to_detail_includes_tree():
    tree = [{"type": "map", "bid": 1}]
    pool = {"id": "nm", "name": "NM", "tree": tree}
    d = pool_to_detail(pool)
    assert d["id"] == "nm"
    assert d["tree"] == tree


def test_pool_to_detail_missing_tree():
    d = pool_to_detail({"id": "x", "name": "X"})
    assert d["tree"] == []


# ── match ─────────────────────────────────────────────────────────────────────

def test_active_to_summary_from_state():
    iface = MagicMock()
    iface.match_id = "abc12345"
    iface._last_state = {
        "qualifier": False, "mode": "auto", "team_names": ["A", "B"],
        "best_of": 11, "ref_name": "ref1", "maps_played": 3, "total_maps": 11, "phase": "pick",
    }
    s = active_to_summary(iface)
    assert s["id"] == "abc12345"
    assert s["active"] is True
    assert s["mode"] == "auto"
    assert s["team_names"] == ["A", "B"]


def test_active_to_summary_empty_state():
    iface = MagicMock()
    iface.match_id = "z"
    iface._last_state = None
    s = active_to_summary(iface)
    assert s["mode"] == "off"
    assert s["team_names"] == []


def test_pending_to_summary():
    payload = {"type": "qualifiers", "mode": "auto", "teams": [{"name": "T1"}], "best_of": 9}
    s = pending_to_summary("match1", payload)
    assert s["status"] == "pending"
    assert s["qualifier"] is True
    assert s["team_names"] == ["T1"]
    assert s["best_of"] == 9


def test_orphan_to_summary():
    row = {
        "match_id": "abc",
        "status": "orphaned",
        "payload_json": json.dumps({"type": "bracket", "teams": [{"name": "A"}, {"name": "B"}], "best_of": 7}),
        "controller_type": "BracketAutoRef",
        "bancho_lobby_id": 555,
        "updated_at": 1700000000,
    }
    s = orphan_to_summary(row)
    assert s["id"] == "abc"
    assert s["orphaned"] is True
    assert s["team_names"] == ["A", "B"]
    assert s["bancho_lobby_id"] == 555
    assert s["orphaned_since"] == 1700000000


# ── user ──────────────────────────────────────────────────────────────────────

def test_user_row_to_response():
    row = (1, 99, "player1", "ref", "irc_user", 1700000000)
    r = user_row_to_response(row)
    assert r["id"] == 1
    assert r["osu_username"] == "player1"
    assert r["role"] == "ref"
    assert r["irc_username"] == "irc_user"
    assert r["created_at"] == 1700000000


def test_user_to_account_response_irc_set():
    user = User(id=1, osu_user_id=99, osu_username="p1", role="host",
                irc_username="irc", irc_password="pass")
    r = user_to_account_response(user)
    assert r["irc_set"] is True
    assert "irc_password" not in r


def test_user_to_account_response_irc_not_set():
    user = User(id=2, osu_user_id=None, osu_username="p2", role="ref",
                irc_username=None, irc_password=None)
    r = user_to_account_response(user)
    assert r["irc_set"] is False


# ── stats ─────────────────────────────────────────────────────────────────────

def test_build_mappool_row():
    row = build_mappool_row(
        bid=100,
        counts={"PICK": 5, "BAN": 2, "PROTECT": 1},
        split_by_bid={100: {"picks_while_protected": 3, "protect_only": 0}},
        avg_by_map={100: 900000},
        acc_by_map={100: 0.975},
        code_by_bid={100: "NM1"},
        order_by_bid={100: 0},
    )
    assert row["beatmap_id"] == 100
    assert row["name"] == "NM1"
    assert row["picks"] == 5
    assert row["bans"] == 2
    assert row["protects_picked"] == 3
    assert row["avg_score"] == 900000
    assert row["pool_order"] == 0


def test_build_mappool_row_missing_bid():
    row = build_mappool_row(
        bid=999,
        counts={},
        split_by_bid={},
        avg_by_map={},
        acc_by_map={},
        code_by_bid={},
        order_by_bid={},
    )
    assert row["name"] is None
    assert row["picks"] == 0
    assert row["pool_order"] == 99999


def test_enrich_leaderboard_rows_empty_scores():
    rows = [{"user_id": 1, "username": "p", "maps_played": 2, "z_sum": 1.5}]
    result = enrich_leaderboard_rows(rows, pd.DataFrame(), lambda r: True, {})
    assert result[0]["user_id"] == 1
    assert "best" not in result[0]


def test_enrich_leaderboard_rows_with_scores():
    rows = [{"user_id": 1, "username": "p", "maps_played": 1, "z_sum": 1.0}]
    scores = pd.DataFrame([{
        "user_id": 1, "username": "p", "beatmap_id": 42,
        "score": 800000, "accuracy": 0.98, "rank": "S",
        "mods": "[]", "passed": True,
    }])
    result = enrich_leaderboard_rows(rows, scores, lambda r: True, {42: "NM1"})
    assert result[0]["avg_score"] == 800000
    assert result[0]["best"]["beatmap_id"] == 42
    assert result[0]["best"]["name"] == "NM1"
