"""Tests for QualifiersAutoRef."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import bancho

from autoref.core.enums import RefMode, Step, WinCondition
from autoref.core.models import Match, PlayableMap, Pool, Ruleset, Team, Timers
from autoref.controllers.qualifiers import QualifiersAutoRef


def make_ruleset():
    r = MagicMock(spec=Ruleset)
    r.vs = 2
    r.gamemode = MagicMock()
    r.gamemode.value = 0
    r.win_condition = WinCondition.SCORE_V2
    r.enforced_mods = ""
    r.team_mode = 0
    r.best_of = 1
    r.bans_per_team = 0
    r.protects_per_team = 0
    return r


def make_match(pool):
    return Match(make_ruleset(), pool, MagicMock(), Team("Red"), Team("Blue"))


def make_qar(pool, runs=1):
    match = make_match(pool)
    ar = QualifiersAutoRef(MagicMock(spec=bancho.BanchoClient), match, "Room",
                           runs=runs, mode=RefMode.AUTO,
                           timers=Timers(between_maps=0, closing=0))
    ar._beatmap_cache = MagicMock()
    ar._beatmap_cache.prefetch = AsyncMock()
    ar._beatmap_cache.get = MagicMock(return_value=None)
    ar.lobby = MagicMock()
    ar.lobby.create = AsyncMock(return_value=1)
    ar.lobby.set_room = AsyncMock()
    ar.lobby.set_mods = AsyncMock()
    ar.lobby.invite = AsyncMock()
    ar.lobby.close = AsyncMock()
    ar.lobby.set_map = AsyncMock()
    ar.lobby.timer = AsyncMock()
    ar.lobby.wait_for_all_ready = AsyncMock()
    ar.lobby.wait_for_timer = AsyncMock()
    ar.lobby.run_cli_input = AsyncMock()
    ar.lobby.start = AsyncMock()
    ar.lobby.wait_for_match_end = AsyncMock(return_value=MagicMock())
    ar.lobby.say = AsyncMock()
    from autoref.core.ref.announcer import Announcer
    ar.announcer = Announcer(ar.lobby, ar.match, ar.timers)
    return ar


# ------------------------------------------------------------------ next_step

def test_next_step_returns_pick_for_each_map():
    pool = Pool("p", PlayableMap(1), PlayableMap(2), PlayableMap(3))
    ar = make_qar(pool)
    for _ in range(3):
        assert ar.next_step(None) == (0, Step.PICK)
        ar._map_index += 1  # simulate await_pick advancing the index


def test_next_step_returns_win_after_pool_exhausted():
    pool = Pool("p", PlayableMap(1))
    ar = make_qar(pool)
    ar._map_index = 1  # simulate pool exhausted
    assert ar.next_step(None) == (0, Step.FINISH)


@pytest.mark.asyncio
async def test_next_step_loops_for_multiple_runs():
    pool = Pool("p", PlayableMap(1), PlayableMap(2))
    ar = make_qar(pool, runs=2)
    for _ in range(4):
        assert ar.next_step(None) == (0, Step.PICK)
        await ar.await_pick(0)
    assert ar.next_step(None) == (0, Step.FINISH)


# ------------------------------------------------------------------ await_pick

@pytest.mark.asyncio
async def test_await_pick_returns_maps_in_order():
    pool = Pool("p", PlayableMap(10), PlayableMap(20), PlayableMap(30))
    ar = make_qar(pool)
    results = [await ar.await_pick(0) for _ in range(3)]
    assert results == [10, 20, 30]


# ------------------------------------------------------------------ full run

@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_run_plays_all_maps(mock_sleep):
    pool = Pool("p", PlayableMap(1, name="NM1"), PlayableMap(2, name="HD1"))
    ar = make_qar(pool)
    await ar.run()
    assert ar.lobby.set_map.call_count == 2
    assert ar.lobby.start.call_count == 2
    ar.lobby.close.assert_called_once()


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_run_plays_all_maps_multiple_runs(mock_sleep):
    pool = Pool("p", PlayableMap(1), PlayableMap(2))
    ar = make_qar(pool, runs=3)
    await ar.run()
    assert ar.lobby.set_map.call_count == 6
    assert ar.lobby.start.call_count == 6


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_run_announces_map_name(mock_sleep):
    pool = Pool("p", PlayableMap(1, name="NM1"))
    ar = make_qar(pool)
    await ar.run()
    say_calls = [c.args[0] for c in ar.lobby.say.call_args_list]
    assert any("NM1" in msg for msg in say_calls)
