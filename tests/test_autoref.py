"""Tests for AutoRef ABC and _find_map."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from autoref.core.base import (
    AutoRef, COMMANDS, Command, _find_map, _find_map_by_input, _find_map_by_input_pick,
)
from autoref.core.enums import MapState, RefMode, Step, WinCondition
from autoref.core.models import Match, PlayableMap, Pool, Ruleset, Team, Timers


# ------------------------------------------------------------------ helpers

def make_ruleset(vs=2, enforced_mods="NF"):
    r = MagicMock(spec=Ruleset)
    r.vs = vs
    r.gamemode = MagicMock()
    r.gamemode.value = 0
    r.win_condition = WinCondition.SCORE_V2
    r.enforced_mods = enforced_mods
    r.team_mode = 2
    r.best_of = 1
    r.bans_per_team = 0
    r.protects_per_team = 0
    return r


def make_match(next_step_rv=None, pool=None):
    if pool is None:
        pool = Pool("pool", PlayableMap(1), PlayableMap(2))
    match = Match(make_ruleset(), pool, MagicMock(), Team("Red"), Team("Blue"))
    return match


class ConcreteAutoRef(AutoRef):
    """Minimal concrete subclass for testing."""
    def __init__(self, *args, steps=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._steps = iter(steps or [(0, Step.WIN)])

    def next_step(self, match_status):
        return next(self._steps)

    async def handle_other(self, team_index):
        pass


def make_autoref(steps=None, match=None):
    import bancho
    client = MagicMock(spec=bancho.BanchoClient)
    client.on = MagicMock()
    if match is None:
        match = make_match()
    ar = ConcreteAutoRef(client, match, "Test Room", steps=steps, mode=RefMode.AUTO)
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
    ar.lobby.channel = MagicMock()
    ar.lobby.channel.on = MagicMock()
    ar.lobby.channel.remove_listener = MagicMock()
    return ar


# ------------------------------------------------------------------ _find_map

def test_find_map_flat():
    pm = PlayableMap(42)
    match = make_match(pool=Pool("p", pm, PlayableMap(1)))
    assert _find_map(match, 42) is pm


def test_find_map_nested():
    pm = PlayableMap(99)
    match = make_match(pool=Pool("outer", Pool("inner", pm), PlayableMap(1)))
    assert _find_map(match, 99) is pm


def test_find_map_missing():
    match = make_match(pool=Pool("p", PlayableMap(1)))
    assert _find_map(match, 999) is None


# ------------------------------------------------------------------ _find_map_by_input

def test_find_map_by_input_exact():
    from autoref.core.base import _find_map_by_input
    pm = PlayableMap(1, name="NM1")
    match = make_match(pool=Pool("p", pm))
    assert _find_map_by_input(match, "NM1") is pm


def test_find_map_by_input_case_insensitive():
    from autoref.core.base import _find_map_by_input
    pm = PlayableMap(1, name="HD2")
    match = make_match(pool=Pool("p", pm))
    assert _find_map_by_input(match, "hd2") is pm


def test_find_map_by_input_space_underscore():
    from autoref.core.base import _find_map_by_input
    pm = PlayableMap(1, name="some map")
    match = make_match(pool=Pool("p", pm))
    assert _find_map_by_input(match, "some_map") is pm


def test_find_map_by_input_no_match():
    from autoref.core.base import _find_map_by_input
    match = make_match(pool=Pool("p", PlayableMap(1, name="NM1")))
    assert _find_map_by_input(match, "DT3") is None


# ban path: PICKABLE only

def test_ban_finds_pickable():
    pm = PlayableMap(1, name="NM1")
    match = make_match(pool=Pool("p", pm))
    assert _find_map_by_input(match, "NM1") is pm


@pytest.mark.parametrize("state", [
    MapState.PROTECTED, MapState.BANNED, MapState.PLAYED, MapState.DISALLOWED,
])
def test_ban_rejects_non_pickable(state):
    pm = PlayableMap(1, name="NM1")
    pm.state = state
    match = make_match(pool=Pool("p", pm))
    assert _find_map_by_input(match, "NM1") is None


# pick path: PICKABLE + PROTECTED

def test_pick_finds_pickable():
    pm = PlayableMap(1, name="NM1")
    match = make_match(pool=Pool("p", pm))
    assert _find_map_by_input_pick(match, "NM1") is pm


def test_pick_finds_protected():
    pm = PlayableMap(1, name="NM1")
    pm.state = MapState.PROTECTED
    match = make_match(pool=Pool("p", pm))
    assert _find_map_by_input_pick(match, "NM1") is pm


@pytest.mark.parametrize("state", [MapState.BANNED, MapState.PLAYED])
def test_pick_rejects_non_playable(state):
    pm = PlayableMap(1, name="NM1")
    pm.state = state
    match = make_match(pool=Pool("p", pm))
    assert _find_map_by_input_pick(match, "NM1") is None


# ------------------------------------------------------------------ _await_map_choice

@pytest.mark.asyncio
async def test_await_map_choice_resolves_on_team_message():
    import bancho
    from autoref.core.base import _find_map_by_input

    pm = PlayableMap(5, name="NM1")
    match = make_match(pool=Pool("p", pm))
    p = MagicMock()
    p.username = "Alice"
    match.teams[0].players = [p]

    ar = make_autoref(match=match)

    captured_handler = {}
    ar.lobby.channel.on = lambda event, fn: captured_handler.update({event: fn})

    async def drive():
        await asyncio.sleep(0)  # let _await_map_choice register handler
        msg = MagicMock()
        msg.user.username = "Alice"
        msg.message = "NM1"
        captured_handler["message"](msg)

    result, _ = await asyncio.gather(ar._await_map_choice(0), drive())
    assert result == 5


@pytest.mark.asyncio
async def test_await_map_choice_ignores_wrong_team():
    import bancho

    pm = PlayableMap(5, name="NM1")
    match = make_match(pool=Pool("p", pm))
    p = MagicMock()
    p.username = "Alice"
    match.teams[0].players = [p]

    ar = make_autoref(match=match)

    captured_handler = {}
    ar.lobby.channel.on = lambda event, fn: captured_handler.update({event: fn})

    resolved = []

    async def drive():
        await asyncio.sleep(0)
        # Wrong team player
        msg = MagicMock()
        msg.user.username = "Bob"
        msg.message = "NM1"
        captured_handler["message"](msg)
        # Correct player
        await asyncio.sleep(0)
        msg2 = MagicMock()
        msg2.user.username = "Alice"
        msg2.message = "NM1"
        captured_handler["message"](msg2)

    result, _ = await asyncio.gather(ar._await_map_choice(0), drive())
    assert result == 5


# ------------------------------------------------------------------ ABC enforcement

def test_cannot_instantiate_autoref_directly():
    import bancho
    with pytest.raises(TypeError):
        AutoRef(MagicMock(spec=bancho.BanchoClient), make_match(), "Room")


def test_must_implement_next_step_and_handle_other():
    import bancho

    class Incomplete(AutoRef):
        def next_step(self, s): return (0, Step.WIN)
        # missing handle_other

    with pytest.raises(TypeError):
        Incomplete(MagicMock(spec=bancho.BanchoClient), make_match(), "Room")


# ------------------------------------------------------------------ Timers

def test_default_timers():
    ar = make_autoref()
    assert ar.timers.pick == 120
    assert ar.timers.ban == 120
    assert ar.timers.between_maps == 10


def test_custom_timers():
    import bancho
    t = Timers(pick=60, ban=30)
    ar = ConcreteAutoRef(MagicMock(spec=bancho.BanchoClient), make_match(), "Room", timers=t)
    ar.lobby = MagicMock()
    assert ar.timers.pick == 60
    assert ar.timers.ban == 30


# ------------------------------------------------------------------ run()

@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_run_creates_and_closes(mock_sleep):
    ar = make_autoref(steps=[(0, Step.WIN)])
    await ar.run()
    ar.lobby.create.assert_called_once_with("Test Room")
    ar.lobby.close.assert_called_once()


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_run_sets_room_and_mods(mock_sleep):
    ar = make_autoref(steps=[(0, Step.WIN)])
    await ar.run()
    ar.lobby.set_room.assert_called_once_with(team_mode=2, score_mode=3, size=4)
    ar.lobby.set_mods.assert_called_once_with("NF")


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_run_skips_mods_when_empty(mock_sleep):
    match = make_match()
    match.ruleset.enforced_mods = ""
    ar = make_autoref(steps=[(0, Step.WIN)], match=match)
    await ar.run()
    ar.lobby.set_mods.assert_not_called()


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_run_invites_players(mock_sleep):
    match = make_match()
    p1, p2 = MagicMock(), MagicMock()
    p1.username, p2.username = "Alice", "Bob"
    match.teams[0].players = [p1]
    match.teams[1].players = [p2]
    ar = make_autoref(steps=[(0, Step.WIN)], match=match)
    await ar.run()
    ar.lobby.invite.assert_any_call("Alice")
    ar.lobby.invite.assert_any_call("Bob")


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_run_announces_win(mock_sleep):
    ar = make_autoref(steps=[(0, Step.WIN)])
    await ar.run()
    ar.lobby.say.assert_called()


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_run_closing_sequence(mock_sleep):
    ar = make_autoref(steps=[(0, Step.WIN)])
    await ar.run()
    mock_sleep.assert_awaited_once_with(ar.timers.closing)
    ar.lobby.close.assert_called_once()


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_run_starts_pick_timer(mock_sleep):
    ar = make_autoref(steps=[(0, Step.PICK), (0, Step.WIN)])
    ar.await_pick = AsyncMock(return_value=1)
    ar.handle_pick = AsyncMock()
    await ar.run()
    ar.lobby.timer.assert_any_call(ar.timers.pick)
    ar.await_pick.assert_called_once_with(0)
    ar.handle_pick.assert_called_once_with(0, 1)


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_run_starts_ban_timer(mock_sleep):
    ar = make_autoref(steps=[(0, Step.BAN), (0, Step.WIN)])
    ar.await_ban = AsyncMock(return_value=2)
    ar.handle_ban = AsyncMock()
    await ar.run()
    ar.lobby.timer.assert_any_call(ar.timers.ban)
    ar.await_ban.assert_called_once_with(0)
    ar.handle_ban.assert_called_once_with(0, 2)


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_run_starts_protect_timer(mock_sleep):
    ar = make_autoref(steps=[(0, Step.PROTECT), (0, Step.WIN)])
    ar.await_protect = AsyncMock(return_value=3)
    ar.handle_protect = AsyncMock()
    await ar.run()
    ar.lobby.timer.assert_any_call(ar.timers.protect)
    ar.await_protect.assert_called_once_with(0)
    ar.handle_protect.assert_called_once_with(0, 3)


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_run_calls_handle_other(mock_sleep):
    called = []

    class TrackingAutoRef(ConcreteAutoRef):
        async def handle_other(self, team_index):
            called.append(team_index)

    import bancho
    ar = TrackingAutoRef(
        MagicMock(spec=bancho.BanchoClient), make_match(), "Room",
        steps=[(1, Step.OTHER), (0, Step.WIN)], mode=RefMode.AUTO,
    )
    ar.lobby = make_autoref().lobby
    await ar.run()
    assert called == [1]


# ------------------------------------------------------------------ play_map()

@pytest.mark.asyncio
async def test_play_map_full_flow():
    ar = make_autoref()
    await ar.play_map(1, 0, Step.PICK)
    ar.lobby.set_map.assert_called_once_with(1, 0)
    ar.lobby.timer.assert_called_with(ar.timers.between_maps)
    ar.lobby.wait_for_all_ready.assert_called_once()
    ar.lobby.wait_for_timer.assert_called_once()
    ar.lobby.start.assert_called_once_with(delay=ar.timers.force_start)
    ar.lobby.wait_for_match_end.assert_called_once()


@pytest.mark.asyncio
async def test_play_map_sets_per_map_mods():
    import aiosu
    pm = PlayableMap(5, mods=aiosu.models.mods.Mods("HD"))
    ar = make_autoref(match=make_match(pool=Pool("p", pm)))
    await ar.play_map(5, 0, Step.PICK)
    # enforced_mods is "NF" in make_ruleset; extra mods "HD" + enforced "NF" = "HDNF"
    ar.lobby.set_mods.assert_called_with("HDNF")


@pytest.mark.asyncio
async def test_play_map_records_action():
    ar = make_autoref()
    await ar.play_map(1, 0, Step.PICK)
    assert len(ar.match.match_status) == 1
    assert ar.match.match_status.iloc[0]["step"] == "PICK"


# ------------------------------------------------------------------ handle_ban/protect

@pytest.mark.asyncio
async def test_handle_ban_records_and_announces():
    ar = make_autoref()
    await ar.handle_ban(0, 1)
    assert len(ar.match.match_status) == 1
    assert ar.match.match_status.iloc[0]["step"] == "BAN"
    ar.lobby.say.assert_called_once()


@pytest.mark.asyncio
async def test_handle_protect_records_and_announces():
    ar = make_autoref()
    await ar.handle_protect(1, 2)
    assert len(ar.match.match_status) == 1
    assert ar.match.match_status.iloc[0]["step"] == "PROTECT"
    ar.lobby.say.assert_called_once()


# ------------------------------------------------------------------ Command dataclass

def test_command_to_dict_keys():
    cmd = Command("undo", ["u"], desc="undo last action", section="flow")
    d = cmd.to_dict()
    assert d["name"] == "undo"
    assert d["aliases"] == ["u"]
    assert d["desc"] == "undo last action"
    assert d["section"] == "flow"
    assert d["scope"] == "ref"
    assert d["noprefix"] is False
    assert d["bracket_only"] is False
    assert ">undo" in d["label"]
    assert ">u" in d["label"]


def test_command_noprefix_label():
    cmd = Command("panic", noprefix=True, scope="anyone")
    label = cmd.to_dict()["label"]
    assert not label.startswith(">")
    assert label.startswith("panic")


def test_command_usage_in_label():
    cmd = Command("next", usage="<map>")
    assert "<map>" in cmd.to_dict()["label"]


def test_command_bracket_only_flag():
    cmd = Command("fp", bracket_only=True)
    assert cmd.to_dict()["bracket_only"] is True


# ------------------------------------------------------------------ COMMANDS registry

def test_commands_registry_not_empty():
    assert len(COMMANDS) > 0
    for c in COMMANDS:
        assert c.name
        assert c.section
        assert c.scope in ("ref", "anyone")


def test_commands_registry_has_panic_noprefix():
    panic = next(c for c in COMMANDS if c.name == "!panic")
    assert panic.noprefix is True
    assert panic.scope == "anyone"


def test_commands_registry_bracket_only_filtered():
    bracket_cmds = [c for c in COMMANDS if c.bracket_only]
    non_bracket = [c for c in COMMANDS if not c.bracket_only]
    assert bracket_cmds and non_bracket


# ------------------------------------------------------------------ score fetcher wiring

@pytest.mark.asyncio
async def test_play_map_spawns_score_fetch_and_stores_results():
    fetcher = MagicMock()
    fetcher.fetch_for_game = AsyncMock(return_value=[
        {"user_id": 11, "score": 900_000, "accuracy": 0.95, "max_combo": 400,
         "mods": ["HD"], "passed": True, "perfect": False, "rank": "S"},
    ])

    match = make_match()
    p = MagicMock(); p.id = 11; p.username = "redA"
    match.teams[0].players = [p]

    ar = make_autoref(match=match)
    ar.score_fetcher = fetcher
    ar.lobby.room_id = 9999
    await ar.play_map(1, 0, Step.PICK)
    # Drain the spawned background task.
    await asyncio.gather(*ar._score_fetch_tasks, return_exceptions=True)

    fetcher.fetch_for_game.assert_awaited_once_with(9999, 1)
    assert match.game_scores
    turn, beatmap_id, scores = match.game_scores[0]
    assert beatmap_id == 1
    # roster annotation applied
    assert scores[0]["username"] == "redA"
    assert scores[0]["team_index"] == 0


@pytest.mark.asyncio
async def test_play_map_no_fetch_without_fetcher():
    ar = make_autoref()
    ar.lobby.room_id = 9999
    assert ar.score_fetcher is None
    await ar.play_map(1, 0, Step.PICK)
    assert ar._score_fetch_tasks == []
    assert ar.match.game_scores == []


@pytest.mark.asyncio
async def test_play_map_no_fetch_when_room_id_none():
    fetcher = MagicMock()
    fetcher.fetch_for_game = AsyncMock(return_value=[])
    ar = make_autoref()
    ar.score_fetcher = fetcher
    ar.lobby.room_id = None
    await ar.play_map(1, 0, Step.PICK)
    fetcher.fetch_for_game.assert_not_called()
