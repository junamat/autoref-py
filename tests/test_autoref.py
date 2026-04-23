"""Tests for AutoRef and _find_map."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from autoref.autoref import AutoRef, _find_map
from autoref.enums import Step, WinCondition
from autoref.models import Match, PlayableMap, Pool, Ruleset, Team


def make_ruleset(vs=2, enforced_mods="NF"):
    r = MagicMock(spec=Ruleset)
    r.vs = vs
    r.gamemode = MagicMock()
    r.gamemode.value = 0
    r.win_condition = WinCondition.SCORE_V2
    r.enforced_mods = enforced_mods
    return r


def make_match(next_step=None, pool=None):
    if pool is None:
        pool = Pool("pool", PlayableMap(1), PlayableMap(2))
    if next_step is None:
        next_step = MagicMock(return_value=(0, Step.WIN))
    return Match(make_ruleset(), pool, next_step, Team("Red"), Team("Blue"))


def make_autoref(match=None):
    client = MagicMock()
    client.on = MagicMock()
    if match is None:
        match = make_match()
    ar = AutoRef.__new__(AutoRef)
    ar._client = client
    ar.match = match
    ar.room_name = "Test Room"
    ar.lobby = MagicMock()
    ar.lobby.create = AsyncMock(return_value=1)
    ar.lobby.set_room = AsyncMock()
    ar.lobby.set_mods = AsyncMock()
    ar.lobby.invite = AsyncMock()
    ar.lobby.close = AsyncMock()
    ar.lobby.set_map = AsyncMock()
    ar.lobby.wait_for_all_ready = AsyncMock()
    ar.lobby.start = AsyncMock()
    ar.lobby.wait_for_match_end = AsyncMock(return_value=MagicMock())
    return ar


# ------------------------------------------------------------------ _find_map

def test_find_map_flat_pool():
    pm = PlayableMap(42)
    pool = Pool("p", pm, PlayableMap(1))
    assert _find_map(Match(make_ruleset(), pool, MagicMock(), Team("A")), 42) is pm


def test_find_map_nested_pool():
    pm = PlayableMap(99)
    inner = Pool("inner", pm)
    outer = Pool("outer", inner, PlayableMap(1))
    match = Match(make_ruleset(), outer, MagicMock(), Team("A"))
    assert _find_map(match, 99) is pm


def test_find_map_not_found():
    pool = Pool("p", PlayableMap(1))
    match = Match(make_ruleset(), pool, MagicMock(), Team("A"))
    assert _find_map(match, 999) is None


# ------------------------------------------------------------------ run()

@pytest.mark.asyncio
async def test_run_creates_and_closes_room():
    ar = make_autoref()
    await ar.run()
    ar.lobby.create.assert_called_once_with("Test Room")
    ar.lobby.close.assert_called_once()


@pytest.mark.asyncio
async def test_run_sets_room_params():
    ar = make_autoref()
    await ar.run()
    ar.lobby.set_room.assert_called_once_with(team_mode=2, score_mode=0, size=4)


@pytest.mark.asyncio
async def test_run_sets_enforced_mods():
    ar = make_autoref()
    await ar.run()
    ar.lobby.set_mods.assert_called_once_with("NF")


@pytest.mark.asyncio
async def test_run_skips_mods_when_falsy():
    match = make_match()
    match.ruleset.enforced_mods = ""
    ar = make_autoref(match)
    await ar.run()
    ar.lobby.set_mods.assert_not_called()


@pytest.mark.asyncio
async def test_run_invites_all_players():
    match = make_match()
    p1, p2 = MagicMock(), MagicMock()
    p1.username = "Alice"
    p2.username = "Bob"
    match.teams[0].players = [p1]
    match.teams[1].players = [p2]
    ar = make_autoref(match)
    await ar.run()
    ar.lobby.invite.assert_any_call("Alice")
    ar.lobby.invite.assert_any_call("Bob")


@pytest.mark.asyncio
async def test_run_raises_on_pick_step():
    match = make_match(next_step=MagicMock(return_value=(0, Step.PICK)))
    ar = make_autoref(match)
    with pytest.raises(NotImplementedError):
        await ar.run()


@pytest.mark.asyncio
async def test_run_raises_on_ban_step():
    match = make_match(next_step=MagicMock(return_value=(0, Step.BAN)))
    ar = make_autoref(match)
    with pytest.raises(NotImplementedError):
        await ar.run()


# ------------------------------------------------------------------ play_map()

@pytest.mark.asyncio
async def test_play_map_sets_map_and_starts():
    ar = make_autoref()
    await ar.play_map(1, 0, Step.PICK)
    ar.lobby.set_map.assert_called_once_with(1, 0)
    ar.lobby.wait_for_all_ready.assert_called_once()
    ar.lobby.start.assert_called_once()
    ar.lobby.wait_for_match_end.assert_called_once()


@pytest.mark.asyncio
async def test_play_map_sets_map_mods_when_present():
    pm = PlayableMap(5, mods="HD")
    pool = Pool("p", pm)
    match = make_match(pool=pool)
    ar = make_autoref(match)
    await ar.play_map(5, 0, Step.PICK)
    ar.lobby.set_mods.assert_called_once_with("HD")


@pytest.mark.asyncio
async def test_play_map_records_action():
    ar = make_autoref()
    await ar.play_map(1, 0, Step.PICK)
    assert len(ar.match.match_status) == 1
    row = ar.match.match_status.iloc[0]
    assert row["beatmap_id"] == 1
    assert row["step"] == "PICK"
