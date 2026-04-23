import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from autoref.enums import Step, WinCondition
from autoref.models import Match, ModdedPool, PlayableMap, Pool, Ruleset, Team


def make_ruleset() -> Ruleset:
    ruleset = MagicMock(spec=Ruleset)
    ruleset.vs = 2
    ruleset.gamemode = MagicMock()
    ruleset.gamemode.name_api = "osu"
    ruleset.win_condition = WinCondition.SCORE_V2
    ruleset.enforced_mods = MagicMock()
    return ruleset


def make_pool() -> Pool:
    maps = [PlayableMap(i) for i in range(1, 5)]
    return Pool("test_pool", *maps)


def make_match(next_step=None) -> Match:
    if next_step is None:
        next_step = MagicMock(return_value=(0, Step.PICK))
    return Match(make_ruleset(), make_pool(), next_step, Team("Alpha"), Team("Beta"))


# --- Pool ---

def test_pool_stores_maps():
    m1, m2 = PlayableMap(1), PlayableMap(2)
    pool = Pool("NM", m1, m2)
    assert pool.maps == [m1, m2]
    assert pool.name == "NM"


def test_pool_nesting():
    nm = Pool("NM", PlayableMap(1))
    hd = Pool("HD", PlayableMap(2))
    full = Pool("Full", nm, hd)
    assert len(full.maps) == 2


def test_modded_pool_carries_mods():
    mods = MagicMock()
    pool = ModdedPool("HD", mods, PlayableMap(1), PlayableMap(2))
    assert pool.mods is mods
    assert len(pool.maps) == 2


# --- Match ---

def test_match_status_initial_schema():
    match = make_match()
    assert list(match.match_status.columns) == ["turn", "team_index", "step", "beatmap_id", "timestamp"]
    assert match.match_status.empty


def test_record_action_appends_row():
    match = make_match()
    match.record_action(0, Step.BAN, 42)
    assert len(match.match_status) == 1
    row = match.match_status.iloc[0]
    assert row["team_index"] == 0
    assert row["step"] == "BAN"
    assert row["beatmap_id"] == 42
    assert row["turn"] == 0


def test_record_action_increments_turn():
    match = make_match()
    match.record_action(0, Step.BAN, 1)
    match.record_action(1, Step.BAN, 2)
    match.record_action(0, Step.PICK, 3)
    assert list(match.match_status["turn"]) == [0, 1, 2]


def test_save_and_resume(tmp_path: Path):
    match = make_match()
    match.record_action(0, Step.BAN, 10)
    match.record_action(1, Step.PICK, 20)

    path = tmp_path / "status.csv"
    match.save(path)

    fresh = make_match()
    fresh.resume(path)

    assert len(fresh.match_status) == 2
    assert list(fresh.match_status["beatmap_id"]) == [10, 20]
    assert list(fresh.match_status["step"]) == ["BAN", "PICK"]


# --- Team (with mocked API) ---

@pytest.mark.asyncio
async def test_team_create_fetches_players():
    mock_user = MagicMock()
    mock_user.id = 123

    mock_client = AsyncMock()
    mock_client.get_user = AsyncMock(return_value=mock_user)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("autoref.models.make_client", return_value=mock_client):
        team = await Team.create("TestTeam", 123)

    assert team.name == "TestTeam"
    assert len(team.players) == 1
    assert team.players[0].id == 123


# --- PlayableMap (with mocked API) ---

@pytest.mark.asyncio
async def test_playable_map_create_fetches_beatmap():
    mock_beatmap = MagicMock()
    mock_beatmap.id = 75

    mock_client = AsyncMock()
    mock_client.get_beatmap = AsyncMock(return_value=mock_beatmap)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("autoref.models.make_client", return_value=mock_client):
        pmap = await PlayableMap.create(75)

    assert pmap.beatmap_id == 75
    assert pmap.beatmap.id == 75
