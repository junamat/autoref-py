"""Tests for VotedQualifiersAutoRef."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import bancho
import pytest

from autoref.controllers.voted import VotedQualifiersAutoRef
from autoref.core.enums import MapState, RefMode, Step, WinCondition
from autoref.core.models import Match, PlayableMap, Pool, Ruleset, Team, Timers

# ------------------------------------------------------------------ helpers

def make_ruleset():
    r = MagicMock(spec=Ruleset)
    r.vs = 1
    r.gamemode = MagicMock()
    r.gamemode.value = 0
    r.win_condition = WinCondition.SCORE_V2
    r.enforced_mods = ""
    r.team_mode = 0
    r.best_of = 1
    r.bans_per_team = 0
    r.protects_per_team = 0
    return r


def make_player(name: str):
    return type("Player", (), {"username": name})()


def make_match(pool, *player_names):
    if not player_names:
        player_names = ("p1", "p2", "p3", "p4")
    teams = [Team(n) for n in player_names]
    for team, name in zip(teams, player_names):
        team.players = [make_player(name)]
    return Match(make_ruleset(), pool, MagicMock(), *teams)


class FakeChannel:
    def __init__(self):
        self._handlers: dict[str, list] = {}

    def on(self, event, fn):
        self._handlers.setdefault(event, []).append(fn)

    def remove_listener(self, event, fn):
        try:
            self._handlers.get(event, []).remove(fn)
        except ValueError:
            pass

    def emit(self, username: str, text: str):
        msg = MagicMock()
        msg.user.username = username
        msg.message = text
        for fn in list(self._handlers.get("message", [])):
            fn(msg)


def make_var(pool, *, runs=1, players=("p1", "p2", "p3", "p4"), seed=42, vote_timeout=5):
    match = make_match(pool, *players)
    ar = VotedQualifiersAutoRef(
        MagicMock(spec=bancho.BanchoClient),
        match,
        "Room",
        runs=runs,
        vote_timeout=vote_timeout,
        empty_grace=10,
        timers=Timers(between_maps=0, closing=0, ready_up=0, start_map=0),
        seed=seed,
        mode=RefMode.AUTO,
    )
    ar._beatmap_cache = MagicMock()
    ar._beatmap_cache.prefetch = AsyncMock()
    ar._beatmap_cache.get = MagicMock(return_value=None)

    channel = FakeChannel()
    lobby = MagicMock()
    lobby.players = set()
    lobby.channel = channel
    lobby.say = AsyncMock()
    lobby.reply = AsyncMock()
    lobby.timer = AsyncMock()
    lobby.abort_timer = AsyncMock()
    lobby.wait_for_timer = AsyncMock()
    lobby.wait_for_all_ready = AsyncMock()
    lobby.wait_for_match_end = AsyncMock(return_value=MagicMock())
    lobby.run_cli_input = AsyncMock()
    lobby.set_map = AsyncMock()
    lobby.set_mods = AsyncMock()
    lobby.start = AsyncMock()
    lobby.add_presence_hook = MagicMock()
    lobby._reply_sinks = {}

    ar.lobby = lobby
    ar.play_map = AsyncMock(return_value=MagicMock())
    ar._save_match = MagicMock()

    # Hydrate active players from teams (skipping _pre_loop)
    for team in match.teams:
        for player in team.players:
            from autoref.core.utils import normalize_name
            ar._active_players.add(normalize_name(player.username))

    return ar


def set_in_lobby(ar, *usernames):
    ar.lobby.players = set(usernames)


async def inject_after_yields(ar, username, text, yields=3):
    """Yield to let coroutine start, then inject a message."""
    for _ in range(yields):
        await asyncio.sleep(0)
    ar.lobby.channel.emit(username, text)


async def fire_timer(ar, yields=1):
    """Set wait_for_timer to complete, yield to let awaiter process it."""
    ar.lobby.wait_for_timer.return_value = None  # already AsyncMock, just ensure no blocking
    for _ in range(yields):
        await asyncio.sleep(0)


# ------------------------------------------------------------------ next_step

def test_next_step_pick_when_maps_remain():
    pool = Pool("p", PlayableMap(1, name="NM1"), PlayableMap(2, name="NM2"))
    ar = make_var(pool, players=("p1",))
    assert ar.next_step(None) == (0, Step.PICK)


def test_next_step_finish_when_all_played():
    pool = Pool("p", PlayableMap(1, name="NM1"), PlayableMap(2, name="NM2"))
    ar = make_var(pool, players=("p1",))
    ar._play_counts = {1: 1, 2: 1}
    assert ar.next_step(None) == (0, Step.FINISH)


def test_next_step_finish_when_no_active_players():
    pool = Pool("p", PlayableMap(1, name="NM1"))
    ar = make_var(pool, players=("p1",))
    ar._active_players.clear()
    assert ar.next_step(None) == (0, Step.FINISH)


def test_next_step_runs_2_not_done_until_2x_pool():
    pool = Pool("p", PlayableMap(1, name="NM1"), PlayableMap(2, name="NM2"))
    ar = make_var(pool, players=("p1",), runs=2)
    ar._play_counts = {1: 1, 2: 1}
    assert ar.next_step(None) == (0, Step.PICK)
    ar._play_counts = {1: 2, 2: 2}
    assert ar.next_step(None) == (0, Step.FINISH)


# ------------------------------------------------------------------ _available_maps

def test_available_maps_runs_1_all_unplayed():
    pool = Pool("p", PlayableMap(1, name="NM1"), PlayableMap(2, name="NM2"))
    ar = make_var(pool, players=("p1",))
    avail = ar._available_maps()
    assert {m.beatmap_id for m in avail} == {1, 2}


def test_available_maps_runs_1_one_played():
    pool = Pool("p", PlayableMap(1, name="NM1"), PlayableMap(2, name="NM2"))
    ar = make_var(pool, players=("p1",))
    ar._play_counts[1] = 1
    avail = ar._available_maps()
    assert [m.beatmap_id for m in avail] == [2]


def test_available_maps_runs_2_floor_advance():
    pool = Pool("p", PlayableMap(1, name="NM1"), PlayableMap(2, name="NM2"), PlayableMap(3, name="NM3"))
    ar = make_var(pool, players=("p1",), runs=2)
    # After first pass: 1 played once, 2 and 3 unplayed → floor=0 → only {2,3} available
    ar._play_counts = {1: 1, 2: 0, 3: 0}
    avail = ar._available_maps()
    assert {m.beatmap_id for m in avail} == {2, 3}


def test_available_maps_runs_2_all_played_once():
    pool = Pool("p", PlayableMap(1, name="NM1"), PlayableMap(2, name="NM2"))
    ar = make_var(pool, players=("p1",), runs=2)
    ar._play_counts = {1: 1, 2: 1}
    avail = ar._available_maps()
    assert {m.beatmap_id for m in avail} == {1, 2}


# ------------------------------------------------------------------ single-player pick

@pytest.mark.asyncio
async def test_single_player_pick():
    pool = Pool("p", PlayableMap(1, name="NM1"), PlayableMap(2, name="NM2"))
    ar = make_var(pool, players=("p1",), seed=42)
    set_in_lobby(ar, "p1")

    timer_event = asyncio.Event()
    async def wait_timer():
        await timer_event.wait()
    ar.lobby.wait_for_timer = wait_timer

    task = asyncio.create_task(ar.await_pick(0))
    # Let task reach the asyncio.wait inside _collect_pick
    for _ in range(5):
        await asyncio.sleep(0)

    # Inject pick message
    ar.lobby.channel.emit("p1", "NM1")
    # Fire timer
    timer_event.set()
    await asyncio.sleep(0)

    result = await task
    assert result == 1


@pytest.mark.asyncio
async def test_single_player_pick_commits_immediately():
    """Single player: pick commits as soon as they type — no waiting for timer close."""
    pool = Pool("p", PlayableMap(1, name="NM1"), PlayableMap(2, name="NM2"))
    ar = make_var(pool, players=("p1",), seed=42)
    set_in_lobby(ar, "p1")

    timer_fired = False
    async def wait_timer():
        nonlocal timer_fired
        await asyncio.sleep(9999)  # never fires in this test
        timer_fired = True
    ar.lobby.wait_for_timer = wait_timer

    task = asyncio.create_task(ar.await_pick(0))
    for _ in range(5):
        await asyncio.sleep(0)

    ar.lobby.channel.emit("p1", "NM1")
    for _ in range(5):
        await asyncio.sleep(0)

    result = await asyncio.wait_for(task, timeout=1.0)
    assert result == 1
    assert not timer_fired


@pytest.mark.asyncio
async def test_single_player_random():
    pool = Pool("p", PlayableMap(10, name="NM1"), PlayableMap(20, name="NM2"))
    ar = make_var(pool, players=("p1",), seed=42)
    set_in_lobby(ar, "p1")

    timer_event = asyncio.Event()
    async def wait_timer():
        await timer_event.wait()
    ar.lobby.wait_for_timer = wait_timer

    task = asyncio.create_task(ar.await_pick(0))
    for _ in range(5):
        await asyncio.sleep(0)

    ar.lobby.channel.emit("p1", "random")
    timer_event.set()
    await asyncio.sleep(0)

    result = await task
    assert result in (10, 20)


@pytest.mark.asyncio
async def test_timer_expiry_random():
    """No input at all → timer fires → random map picked."""
    pool = Pool("p", PlayableMap(10, name="NM1"), PlayableMap(20, name="NM2"))
    ar = make_var(pool, players=("p1",), seed=42)
    set_in_lobby(ar, "p1")

    timer_event = asyncio.Event()
    async def wait_timer():
        await timer_event.wait()
    ar.lobby.wait_for_timer = wait_timer

    task = asyncio.create_task(ar.await_pick(0))
    for _ in range(5):
        await asyncio.sleep(0)

    timer_event.set()
    await asyncio.sleep(0)

    result = await task
    assert result in (10, 20)


# ------------------------------------------------------------------ multi-player pass chain

@pytest.mark.asyncio
async def test_multi_player_pass_chain():
    """3 players: first two pass, third picks."""
    pool = Pool("p", PlayableMap(1, name="NM1"), PlayableMap(2, name="NM2"))
    ar = make_var(pool, players=("a", "b", "c"), seed=0)
    set_in_lobby(ar, "a", "b", "c")

    timer_event = asyncio.Event()
    async def wait_timer():
        await timer_event.wait()
        timer_event.clear()  # reset for next call
    ar.lobby.wait_for_timer = wait_timer

    task = asyncio.create_task(ar.await_pick(0))

    # Candidates after shuffle with seed=0: deterministic order
    # We'll just let whoever gets the turn pass or pick
    passed = []

    for _ in range(3):
        # Let the task reach the asyncio.wait
        for _ in range(5):
            await asyncio.sleep(0)

        # Figure out who the current picker is
        picker = ar._current_picker
        if picker is None:
            break
        if len(passed) < 2:
            # First two pass
            ar.lobby.channel.emit(picker, "pass")
            passed.append(picker)
            for _ in range(3):
                await asyncio.sleep(0)
        else:
            # Third picks
            ar.lobby.channel.emit(picker, "NM1")
            timer_event.set()
            break

    result = await task
    assert result in (1, 2)


@pytest.mark.asyncio
async def test_all_pass_random():
    """Every player passes → random map rolled."""
    pool = Pool("p", PlayableMap(1, name="NM1"), PlayableMap(2, name="NM2"))
    ar = make_var(pool, players=("a", "b"), seed=42)
    set_in_lobby(ar, "a", "b")

    timer_event = asyncio.Event()
    async def wait_timer():
        await timer_event.wait()
        timer_event.clear()
    ar.lobby.wait_for_timer = wait_timer

    task = asyncio.create_task(ar.await_pick(0))

    for _ in range(2):
        for _ in range(5):
            await asyncio.sleep(0)
        picker = ar._current_picker
        if picker is None:
            break
        ar.lobby.channel.emit(picker, "pass")
        for _ in range(3):
            await asyncio.sleep(0)

    result = await task
    assert result in (1, 2)
    # Log should record all-passed-random
    assert ar._vote_log[-1]["via"] == "all-passed-random"


# ------------------------------------------------------------------ quit

@pytest.mark.asyncio
async def test_quit_removes_player():
    pool = Pool("p", PlayableMap(1, name="NM1"))
    ar = make_var(pool, players=("p1", "p2"))
    assert "p1" in ar._active_players

    await ar._handle_quit("p1")

    assert "p1" not in ar._active_players
    assert "p1" in ar._quit_players
    ar.lobby.say.assert_called()


@pytest.mark.asyncio
async def test_quit_via_cli_rejected():
    pool = Pool("p", PlayableMap(1, name="NM1"))
    ar = make_var(pool, players=("p1",))
    ar.lobby._reply_sinks = {"cli": MagicMock()}

    await ar._handle_quit("cli")

    assert "cli" not in ar._quit_players
    ar.lobby.reply.assert_called()


@pytest.mark.asyncio
async def test_finish_when_all_quit():
    pool = Pool("p", PlayableMap(1, name="NM1"))
    ar = make_var(pool, players=("p1",))
    ar._active_players.clear()
    assert ar.next_step(None) == (0, Step.FINISH)


@pytest.mark.asyncio
async def test_quit_picker_mid_vote():
    """Picker quits mid-vote → await_pick returns None (main loop re-evaluates).
    On re-call, remaining player picks successfully."""
    pool = Pool("p", PlayableMap(1, name="NM1"), PlayableMap(2, name="NM2"))
    ar = make_var(pool, players=("a", "b"), seed=42)
    set_in_lobby(ar, "a", "b")

    timer_event = asyncio.Event()
    async def wait_timer():
        await timer_event.wait()
        timer_event.clear()
    ar.lobby.wait_for_timer = wait_timer

    # First await_pick: picker quits mid-vote → returns None
    task = asyncio.create_task(ar.await_pick(0))
    for _ in range(5):
        await asyncio.sleep(0)

    first_picker = ar._current_picker
    assert first_picker is not None
    await ar._handle_quit(first_picker)
    for _ in range(5):
        await asyncio.sleep(0)

    result1 = await task
    assert result1 is None  # cancelled by quit

    # After quit, first_picker removed from active set
    assert first_picker not in ar._active_players

    # Second await_pick: only the remaining player is active
    task2 = asyncio.create_task(ar.await_pick(0))
    for _ in range(5):
        await asyncio.sleep(0)

    other_picker = ar._current_picker
    assert other_picker is not None
    assert other_picker != first_picker

    ar.lobby.channel.emit(other_picker, "NM1")
    timer_event.set()

    result2 = await task2
    assert result2 in (1, 2)


# ------------------------------------------------------------------ runs=2

def test_runs_2_no_repeat_until_floor():
    pool = Pool("p", PlayableMap(1, name="NM1"), PlayableMap(2, name="NM2"), PlayableMap(3, name="NM3"))
    ar = make_var(pool, players=("p1",), runs=2)
    # Play NM1 once
    ar._play_counts[1] = 1
    avail = ar._available_maps()
    assert 1 not in {m.beatmap_id for m in avail}
    assert {m.beatmap_id for m in avail} == {2, 3}


@pytest.mark.asyncio
async def test_runs_2_completes_after_2x_pool():
    pool = Pool("p", PlayableMap(1, name="NM1"), PlayableMap(2, name="NM2"))
    ar = make_var(pool, players=("p1",), runs=2)
    ar._play_counts = {1: 2, 2: 2}
    assert ar.next_step(None) == (0, Step.FINISH)


# ------------------------------------------------------------------ invalid map handling

@pytest.mark.asyncio
async def test_invalid_map_keeps_listening():
    """Bad map name → error message sent, listener stays active, timer still picks."""
    pool = Pool("p", PlayableMap(1, name="NM1"), PlayableMap(2, name="NM2"))
    ar = make_var(pool, players=("p1",), seed=42)
    set_in_lobby(ar, "p1")

    timer_event = asyncio.Event()
    async def wait_timer():
        await timer_event.wait()
    ar.lobby.wait_for_timer = wait_timer

    task = asyncio.create_task(ar.await_pick(0))
    for _ in range(5):
        await asyncio.sleep(0)

    ar.lobby.channel.emit("p1", "BOGUS")
    for _ in range(3):
        await asyncio.sleep(0)

    # Should have said an error
    say_calls = [str(c) for c in ar.lobby.say.call_args_list]
    assert any("BOGUS" in s or "Unknown" in s for s in say_calls)

    # Timer still works — fires → random map
    ar.lobby.channel.emit("p1", "NM1")
    timer_event.set()
    result = await task
    assert result == 1


# ------------------------------------------------------------------ lobby leave / grace

@pytest.mark.asyncio
async def test_all_leave_lobby_no_quit_pauses():
    """All players leave lobby (no quit) → await_pick blocks on repopulated event."""
    pool = Pool("p", PlayableMap(1, name="NM1"))
    ar = make_var(pool, players=("p1",), seed=42)
    set_in_lobby(ar)  # nobody in lobby initially

    timer_event = asyncio.Event()
    async def wait_timer():
        await timer_event.wait()
    ar.lobby.wait_for_timer = wait_timer

    task = asyncio.create_task(ar.await_pick(0))
    for _ in range(5):
        await asyncio.sleep(0)

    # Task should be blocking on _lobby_repopulated
    assert not task.done()

    # Player rejoins
    set_in_lobby(ar, "p1")
    ar._lobby_repopulated.set()
    for _ in range(5):
        await asyncio.sleep(0)

    # Now it proceeds to pick
    ar.lobby.channel.emit("p1", "NM1")
    timer_event.set()
    result = await task
    assert result == 1


@pytest.mark.asyncio
async def test_player_rejoin_after_leave_eligible():
    pool = Pool("p", PlayableMap(1, name="NM1"))
    ar = make_var(pool, players=("p1",), seed=42)
    # p1 is active but not in lobby
    set_in_lobby(ar)
    assert ar._effective_pickers() == []

    # Rejoin
    set_in_lobby(ar, "p1")
    assert ar._effective_pickers() == ["p1"]


@pytest.mark.asyncio
async def test_grace_timer_closes_lobby():
    pool = Pool("p", PlayableMap(1, name="NM1"))
    ar = make_var(pool, players=("p1",), seed=42)
    set_in_lobby(ar)  # empty lobby

    with patch("asyncio.sleep", new_callable=AsyncMock):
        ar._grace_deadline = asyncio.get_event_loop().time() - 1  # already expired
        ar._grace_task = asyncio.create_task(ar._grace_close_when_expired())
        await ar._grace_task

    assert ar._close_event.is_set()


@pytest.mark.asyncio
async def test_grace_cancelled_on_rejoin():
    pool = Pool("p", PlayableMap(1, name="NM1"))
    ar = make_var(pool, players=("p1",), seed=42)
    set_in_lobby(ar)

    ar._ensure_grace_running()
    assert ar._grace_task is not None
    assert not ar._grace_task.done()

    set_in_lobby(ar, "p1")
    ar._cancel_grace()

    assert ar._grace_task is None


@pytest.mark.asyncio
async def test_late_join_eligible_for_next_vote():
    pool = Pool("p", PlayableMap(1, name="NM1"))
    ar = make_var(pool, players=("p1",), seed=42)
    # p1 is in _active_players but not lobby
    assert "p1" in ar._active_players
    set_in_lobby(ar, "p1")
    # Now effective
    assert "p1" in ar._effective_pickers()


# ------------------------------------------------------------------ picker absent at close

@pytest.mark.asyncio
async def test_picker_absent_at_close_voids_pick():
    """Picker types valid map then leaves before timer fires → pick voided."""
    pool = Pool("p", PlayableMap(1, name="NM1"), PlayableMap(2, name="NM2"))
    ar = make_var(pool, players=("a", "b"), seed=42)
    set_in_lobby(ar, "a", "b")

    timer_event = asyncio.Event()
    async def wait_timer():
        await timer_event.wait()
        timer_event.clear()
    ar.lobby.wait_for_timer = wait_timer

    task = asyncio.create_task(ar.await_pick(0))
    for _ in range(5):
        await asyncio.sleep(0)

    # Find the first picker (deterministic with seed=42)
    first_picker = ar._current_picker
    assert first_picker is not None

    # They type a pick then leave
    ar.lobby.channel.emit(first_picker, "NM1")
    for _ in range(3):
        await asyncio.sleep(0)

    # They leave the lobby
    ar.lobby.players.discard(first_picker)

    # Timer fires: picker absent → pick voided; rotation goes to next candidate
    timer_event.set()
    for _ in range(5):
        await asyncio.sleep(0)

    # Next picker should be active
    next_picker = ar._current_picker
    if next_picker:
        ar.lobby.channel.emit(next_picker, "NM2")
        timer_event.set()

    result = await task
    assert result in (1, 2)


@pytest.mark.asyncio
async def test_pass_drops_from_wheel_not_a_vote():
    """pass does not get presence-checked at close; it commits immediately."""
    pool = Pool("p", PlayableMap(1, name="NM1"), PlayableMap(2, name="NM2"))
    ar = make_var(pool, players=("a", "b"), seed=42)
    set_in_lobby(ar, "a", "b")

    timer_event = asyncio.Event()
    async def wait_timer():
        await timer_event.wait()
        timer_event.clear()
    ar.lobby.wait_for_timer = wait_timer

    task = asyncio.create_task(ar.await_pick(0))
    for _ in range(5):
        await asyncio.sleep(0)

    first_picker = ar._current_picker
    assert first_picker is not None

    # Pass — should NOT wait for timer
    ar.lobby.channel.emit(first_picker, "pass")
    for _ in range(5):
        await asyncio.sleep(0)

    # Rotation should move to next picker without timer needing to fire
    next_picker = ar._current_picker
    assert next_picker is not None
    assert next_picker != first_picker

    ar.lobby.channel.emit(next_picker, "NM1")
    timer_event.set()
    result = await task
    assert result in (1, 2)


# ------------------------------------------------------------------ commands

@pytest.mark.asyncio
async def test_quit_command_via_chat():
    pool = Pool("p", PlayableMap(1, name="NM1"))
    ar = make_var(pool, players=("p1",))
    ar.lobby._reply_sinks = {}

    await ar._dispatch_command("quit", [], "p1")

    assert "p1" not in ar._active_players
    ar.lobby.say.assert_called()


@pytest.mark.asyncio
async def test_quit_via_cli_rejected_via_dispatch():
    pool = Pool("p", PlayableMap(1, name="NM1"))
    ar = make_var(pool, players=("p1",))
    ar.lobby._reply_sinks = {"cli": MagicMock()}

    await ar._dispatch_command("quit", [], "cli")

    assert "p1" in ar._active_players
    ar.lobby.reply.assert_called()


@pytest.mark.asyncio
async def test_seed_command_reveals_value():
    pool = Pool("p", PlayableMap(1, name="NM1"))
    ar = make_var(pool, players=("p1",), seed=12345)

    await ar._dispatch_command("seed", [], "p1")

    call_args = " ".join(str(c) for c in ar.lobby.say.call_args_list)
    assert "12345" in call_args


@pytest.mark.asyncio
async def test_reseed_changes_rng_output():
    pool = Pool("p", PlayableMap(1, name="NM1"), PlayableMap(2, name="NM2"))
    ar = make_var(pool, players=("p1",), seed=42)

    before = ar._rng.choice([1, 2, 3, 4, 5])  # noqa: F841
    await ar._dispatch_command("reseed", ["999"], "ref")
    after = ar._rng.choice([1, 2, 3, 4, 5])

    assert ar._seed == 999
    # Choice after reseed follows the new seed
    import random
    expected = random.Random(999).choice([1, 2, 3, 4, 5])
    assert after == expected


@pytest.mark.asyncio
async def test_quit_works_for_non_ref_when_refs_set():
    """With refs allowlist set, non-ref player can still use scope='anyone' quit."""
    pool = Pool("p", PlayableMap(1, name="NM1"))
    ar = make_var(pool, players=("p1",))
    ar.refs = {"some_ref"}  # p1 is not a ref
    ar.lobby._reply_sinks = {}

    await ar._dispatch_command("quit", [], "p1")

    assert "p1" not in ar._active_players


@pytest.mark.asyncio
async def test_seed_replay_reproduces_pick_order():
    pool = Pool("p", PlayableMap(1, name="NM1"), PlayableMap(2, name="NM2"), PlayableMap(3, name="NM3"))
    ar1 = make_var(pool, players=("a", "b", "c"), seed=77)
    ar2 = make_var(pool, players=("a", "b", "c"), seed=77)

    # Both should produce same shuffle order
    cands1 = ["a", "b", "c"]
    cands2 = ["a", "b", "c"]
    ar1._rng.shuffle(cands1)
    ar2._rng.shuffle(cands2)
    assert cands1 == cands2


# ------------------------------------------------------------------ vote log

@pytest.mark.asyncio
async def test_history_log_records_entries():
    pool = Pool("p", PlayableMap(1, name="NM1"), PlayableMap(2, name="NM2"))
    ar = make_var(pool, players=("p1",), seed=42)
    set_in_lobby(ar, "p1")

    timer_event = asyncio.Event()
    async def wait_timer():
        await timer_event.wait()
    ar.lobby.wait_for_timer = wait_timer

    task = asyncio.create_task(ar.await_pick(0))
    for _ in range(5):
        await asyncio.sleep(0)

    ar.lobby.channel.emit("p1", "NM1")
    timer_event.set()
    result = await task  # noqa: F841

    assert len(ar._vote_log) == 1
    entry = ar._vote_log[0]
    assert entry["picker"] == "p1"
    assert entry["via"] == "chosen"
    assert entry["map"] == "NM1"


@pytest.mark.asyncio
async def test_fortune_uses_seeded_rng():
    pool = Pool("p", PlayableMap(1, name="NM1"))
    ar1 = make_var(pool, players=("p1",), seed=42)
    ar2 = make_var(pool, players=("p1",), seed=42)
    set_in_lobby(ar1, "p1")
    set_in_lobby(ar2, "p1")

    # Both use same seed so fortune should be same
    await ar1._handle_fortune("p1")
    await ar2._handle_fortune("p1")

    msg1 = ar1.lobby.say.call_args[0][0]
    msg2 = ar2.lobby.say.call_args[0][0]
    assert msg1 == msg2


@pytest.mark.asyncio
async def test_consensus_alignment():
    pool = Pool("p", PlayableMap(1, name="NM1"), PlayableMap(2, name="NM2"))
    ar = make_var(pool, players=("a", "b"), runs=2, seed=42)

    # Simulate both players picking NM1
    ar._vote_log = [
        {"picker": "a", "map": "NM1", "via": "chosen", "passers": []},
        {"picker": "b", "map": "NM1", "via": "chosen", "passers": []},
        {"picker": "a", "map": "NM2", "via": "chosen", "passers": []},
    ]

    await ar._handle_consensus("anyone")

    calls = [c[0][0] for c in ar.lobby.say.call_args_list]
    # alignment for a: NM1(2 pickers → +1), NM2(1 picker → +0) = 1
    # alignment for b: NM1(2 pickers → +1) = 1
    assert any("most-picked" in c for c in calls)
    assert any("crowd-alignment" in c for c in calls)
