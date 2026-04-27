"""Tests for BracketAutoRef state machine."""
from unittest.mock import AsyncMock, MagicMock

import pytest
import bancho

from autoref.controllers.bracket import BracketAutoRef, Phase
from autoref.core.base import _find_map_by_input, _find_map_by_input_pick
from autoref.core.enums import MapState, RefMode, Step, WinCondition
from autoref.core.lobby import MatchResult, PlayerResult
from autoref.core.models import (
    Match, OrderScheme, PlayableMap, Pool, Ruleset, Team,
)


# ---------------------------------------------------------------- helpers

def make_ruleset(*, best_of=1, bans=0, protects=0, schemes=None, teams=2):
    r = MagicMock(spec=Ruleset)
    r.vs = 1
    r.gamemode = MagicMock()
    r.gamemode.value = 0
    r.win_condition = WinCondition.SCORE_V2
    r.enforced_mods = ""
    r.team_mode = 0
    r.best_of = best_of
    r.bans_per_team = bans
    r.protects_per_team = protects
    r.schemes = schemes
    r.wins_needed = best_of // 2 + 1
    r.bans_for = (lambda i: bans[i] if isinstance(bans, list) else bans)
    r.protects_for = (lambda i: protects[i] if isinstance(protects, list) else protects)
    return r


def make_pool(with_tb=False):
    maps = [PlayableMap(i, name=f"M{i}") for i in range(1, 7)]
    if with_tb:
        maps.append(PlayableMap(99, name="TB", is_tiebreaker=True))
    return Pool("p", *maps)


def _player(username):
    p = MagicMock()
    p.username = username
    return p


def make_team(name, *usernames):
    t = Team(name)
    t.players = [_player(u) for u in usernames]
    return t


def make_bracket(*, best_of=1, bans=0, protects=0, schemes=None,
                 teams=("Red", "Blue"), with_tb=False):
    if schemes is None:
        schemes = [OrderScheme("default")]
    r = make_ruleset(best_of=best_of, bans=bans, protects=protects, schemes=schemes)
    team_objs = tuple(make_team(n, f"{n.lower()}1") for n in teams)
    pool = make_pool(with_tb=with_tb)
    match = Match(r, pool, MagicMock(), *team_objs)
    ar = BracketAutoRef(
        MagicMock(spec=bancho.BanchoClient), match, "Room",
        schemes=schemes,
    )
    ar.lobby = MagicMock()
    return ar


# ---------------------------------------------------------------- init

def test_init_default_scheme_when_none_provided():
    ar = make_bracket()
    ar.schemes = [OrderScheme("x")]  # sanity
    assert ar.phase == Phase.ROLL
    assert ar.ranking is None
    assert ar.scheme is None


def test_init_flips_tb_to_disallowed():
    ar = make_bracket(with_tb=True)
    tb = next(m for m in ar.match.pool.maps if getattr(m, "is_tiebreaker", False))
    assert tb.state == MapState.DISALLOWED


def test_init_leaves_non_tb_alone():
    ar = make_bracket(with_tb=True)
    normals = [m for m in ar.match.pool.maps if not getattr(m, "is_tiebreaker", False)]
    for m in normals:
        assert m.state == MapState.PICKABLE


# ---------------------------------------------------------------- precompute

def test_compute_seq_symmetric_bans_2_teams():
    ar = make_bracket(bans=2)
    ar.set_ranking([0, 1])
    ar.commit_scheme(OrderScheme("s", ban_first=0))
    # ABAB with 2 bans each, starting team 0: 0, 1, 0, 1
    assert ar._ban_seq == [0, 1, 0, 1]


def test_compute_seq_asymmetric_protects():
    ar = make_bracket(protects=[2, 1])
    ar.set_ranking([0, 1])
    ar.commit_scheme(OrderScheme("s", protect_first=0))
    # team 0 owes 2, team 1 owes 1: 0, 1, 0
    assert ar._protect_seq == [0, 1, 0]


def test_compute_seq_loser_first():
    ar = make_bracket(bans=1)
    ar.set_ranking([1, 0])
    ar.commit_scheme(OrderScheme("s", ban_first=0))
    # first_rank=0 = rank 0 = ranking[0] = team 1; then rank 1 = team 0
    assert ar._ban_seq == [1, 0]


def test_compute_seq_abba_2_bans_each():
    ar = make_bracket(bans=2)
    ar.set_ranking([0, 1])
    ar.commit_scheme(OrderScheme("s", ban_first=0, ban_pattern="ABBA"))
    # ABAB -> 0,1,0,1; ABBA swap -> 0,1,1,0
    assert ar._ban_seq == [0, 1, 1, 0]


# ---------------------------------------------------------------- state machine

def test_next_step_protect_then_ban_then_pick():
    pass  # TODO: implement


# ---------------------------------------------------------------- score counting

def test_map_winner_counts_all_scores():
    """Test that _map_winner correctly determines winner from player scores."""
    ar = make_bracket(teams=("Blue", "Red"))
    
    # Create a match result with scores from both teams
    # Teams are created with usernames "blue1" and "red1" by make_bracket
    result = MatchResult()
    result.scores = [
        PlayerResult("red1", 310288, True),    # Red team (team 1)
        PlayerResult("blue1", 472183, True),   # Blue team (team 0)
    ]
    
    # Blue team (team 0) should win with higher score
    winner = ar._map_winner(result)
    assert winner == 0  # Blue team index


def test_map_winner_counts_failed_scores():
    """Test that failed scores are excluded from team total."""
    ar = make_bracket(teams=("Blue", "Red"))
    
    result = MatchResult()
    result.scores = [
        PlayerResult("blue1", 100000, False),  # Blue team, failed - excluded
        PlayerResult("red1", 50000, True),     # Red team, passed
    ]
    
    # Red team should win because blue failed
    winner = ar._map_winner(result)
    assert winner == 1


def test_map_winner_returns_none_on_tie():
    """Test that ties return None."""
    ar = make_bracket(teams=("Blue", "Red"))
    
    result = MatchResult()
    result.scores = [
        PlayerResult("blue1", 100000, True),
        PlayerResult("red1", 100000, True),
    ]
    
    winner = ar._map_winner(result)
    assert winner is None


def test_map_winner_returns_none_on_empty_result():
    """Test that empty or None results return None."""
    ar = make_bracket()
    
    assert ar._map_winner(None) is None
    assert ar._map_winner(MatchResult()) is None
    ar = make_bracket(best_of=1, bans=1, protects=1)
    ar.set_ranking([0, 1])
    ar.commit_scheme(OrderScheme("s"))
    assert ar.next_step(None) == (0, Step.PROTECT)
    assert ar.next_step(None) == (1, Step.PROTECT)
    assert ar.next_step(None) == (0, Step.BAN)
    assert ar.next_step(None) == (1, Step.BAN)
    assert ar.next_step(None) == (0, Step.PICK)  # pick_first=0 + no prior map


def test_next_step_pick_alternates_abab():
    ar = make_bracket(best_of=5)
    ar.set_ranking([0, 1])
    ar.commit_scheme(OrderScheme("s", pick_first=0))
    t1, _ = ar.next_step(None)
    assert t1 == 0   # first pick: rank-0 team
    t2, _ = ar.next_step(None)
    assert t2 == 1   # second pick: rank-1 team
    t3, _ = ar.next_step(None)
    assert t3 == 0   # third pick: back to rank-0


def test_next_step_wins_ends_match():
    ar = make_bracket(best_of=1)
    ar.set_ranking([0, 1])
    ar.commit_scheme(OrderScheme("s"))
    ar._wins[1] = 1
    ti, step = ar.next_step(None)
    assert (ti, step) == (1, Step.WIN)
    assert ar.phase == Phase.DONE


def test_next_step_tb_triggers_when_tied_at_brink():
    ar = make_bracket(best_of=5, with_tb=True)
    ar.set_ranking([0, 1])
    ar.commit_scheme(OrderScheme("s"))
    ar._wins = [2, 2]  # wins_needed=3, both at brink
    ti, step = ar.next_step(None)
    assert step == Step.OTHER
    assert ar.phase == Phase.TB
    assert ar._tb_triggered


def test_next_step_tb_does_not_retrigger():
    ar = make_bracket(best_of=5, with_tb=True)
    ar.set_ranking([0, 1])
    ar.commit_scheme(OrderScheme("s"))
    ar._wins = [2, 2]
    ar.next_step(None)  # triggers TB
    ar._last_map_winner = 0
    # now whatever we return shouldn't be OTHER again
    ti, step = ar.next_step(None)
    assert step != Step.OTHER


def test_split_bans_interleave_with_picks():
    ar = make_bracket(best_of=5, bans=2)
    ar.set_ranking([0, 1])
    ar.commit_scheme(OrderScheme("s", split_ban_after_pick=1))
    # 4 total bans, half-split: 2 before picks, 2 after 1 pick
    assert ar.next_step(None) == (0, Step.BAN)
    assert ar.next_step(None) == (1, Step.BAN)
    # now picks: pick 1
    assert ar.next_step(None)[1] == Step.PICK
    # after 1 pick, second ban half kicks in
    assert ar.next_step(None) == (0, Step.BAN)
    assert ar.next_step(None) == (1, Step.BAN)
    # then picks again
    assert ar.next_step(None)[1] == Step.PICK


def test_no_protects_or_bans_goes_straight_to_pick():
    ar = make_bracket(best_of=1)
    ar.set_ranking([0, 1])
    ar.commit_scheme(OrderScheme("s"))
    assert ar.next_step(None) == (0, Step.PICK)


# ---------------------------------------------------------------- next_picker

def test_next_picker_raises_for_3_teams():
    r = make_ruleset()
    teams = tuple(make_team(n, f"{n}1") for n in ("A", "B", "C"))
    pool = make_pool()
    match = Match(r, pool, MagicMock(), *teams)
    ar = BracketAutoRef(
        MagicMock(spec=bancho.BanchoClient), match, "R",
        schemes=[OrderScheme("s")],
    )
    ar.lobby = MagicMock()
    ar.set_ranking([0, 1, 2])
    ar.commit_scheme(OrderScheme("s"))
    with pytest.raises(NotImplementedError):
        ar.next_picker(None)


# ---------------------------------------------------------------- _map_winner

def test_map_winner_picks_highest_team_score():
    ar = make_bracket()
    # override teams to have multiple players
    ar.match.teams = (make_team("Red", "r1", "r2"), make_team("Blue", "b1", "b2"))
    result = MatchResult(scores=[
        PlayerResult("r1", 500_000, True),
        PlayerResult("r2", 400_000, True),
        PlayerResult("b1", 600_000, True),
        PlayerResult("b2", 200_000, True),
    ])
    assert ar._map_winner(result) == 0  # red totals 900k, blue 800k


def test_map_winner_none_on_tie():
    ar = make_bracket()
    result = MatchResult(scores=[
        PlayerResult("red1", 500_000, True),
        PlayerResult("blue1", 500_000, True),
    ])
    assert ar._map_winner(result) is None


def test_map_winner_counts_failed_players():
    """Failed players are excluded from team total."""
    ar = make_bracket()
    result = MatchResult(scores=[
        PlayerResult("red1", 999_999, False),   # failed - excluded
        PlayerResult("blue1", 100_000, True),
    ])
    assert ar._map_winner(result) == 1  # Blue team wins


def test_map_winner_none_on_empty():
    ar = make_bracket()
    assert ar._map_winner(MatchResult(scores=[])) is None
    assert ar._map_winner(None) is None


def test_map_winner_both_zero_is_tie():
    ar = make_bracket()
    result = MatchResult(scores=[
        PlayerResult("red1", 0, False),
        PlayerResult("blue1", 0, False),
    ])
    assert ar._map_winner(result) is None


def test_map_winner_one_team_zero_other_nonzero():
    """A team whose only score failed loses to a team with a passed score."""
    ar = make_bracket()
    result = MatchResult(scores=[
        PlayerResult("red1", 0, False),
        PlayerResult("blue1", 1, True),
    ])
    assert ar._map_winner(result) == 1


def test_map_winner_unknown_player_ignored():
    ar = make_bracket()
    result = MatchResult(scores=[
        PlayerResult("spectator", 999_999, True),  # not on any team
        PlayerResult("blue1", 100, True),
    ])
    assert ar._map_winner(result) == 1


# ---------------------------------------------------------------- handle_pick map state

def _bracket_with_lobby_for_play_map():
    ar = make_bracket()
    ar.lobby.set_map = AsyncMock()
    ar.lobby.timer = AsyncMock()
    ar.lobby.wait_for_all_ready = AsyncMock()
    ar.lobby.wait_for_timer = AsyncMock()
    ar.lobby.start = AsyncMock()
    ar.lobby.wait_for_match_end = AsyncMock(return_value=MatchResult())
    ar.lobby.say = AsyncMock()
    return ar, ar.match.pool.maps


@pytest.mark.asyncio
async def test_handle_pick_marks_map_played():
    ar, maps = _bracket_with_lobby_for_play_map()
    await ar.handle_pick(0, maps[0].beatmap_id)
    assert maps[0].state == MapState.PLAYED


@pytest.mark.asyncio
async def test_played_map_not_pickable_again():
    ar, maps = _bracket_with_lobby_for_play_map()
    await ar.handle_pick(0, maps[0].beatmap_id)
    assert _find_map_by_input(ar.match, maps[0].name) is None
    assert _find_map_by_input_pick(ar.match, maps[0].name) is None


@pytest.mark.asyncio
async def test_undo_resets_played_to_pickable():
    ar, maps = _bracket_with_lobby_for_play_map()
    await ar.handle_pick(0, maps[0].beatmap_id)
    assert maps[0].state == MapState.PLAYED
    await ar._undo_last_action()
    assert maps[0].state == MapState.PICKABLE


# ---------------------------------------------------------------- commands

def _fake_msg(username, message):
    m = MagicMock()
    m.user = MagicMock()
    m.user.username = username
    m.message = message
    return m


@pytest.mark.asyncio
async def test_command_roll_with_team_names():
    ar = make_bracket()
    ar.lobby.say = AsyncMock()
    handled = await ar._dispatch_command("roll", ["Blue", "Red"], "cli")
    assert handled
    assert ar.ranking == [1, 0]
    assert ar._roll_done.is_set()


@pytest.mark.asyncio
async def test_command_roll_with_indices():
    ar = make_bracket()
    ar.lobby.say = AsyncMock()
    await ar._dispatch_command("roll", ["1", "0"], "cli")
    assert ar.ranking == [1, 0]


@pytest.mark.asyncio
async def test_command_roll_rejects_duplicate():
    ar = make_bracket()
    ar.lobby.say = AsyncMock()
    await ar._dispatch_command("roll", ["Red", "Red"], "cli")
    assert ar.ranking is None


@pytest.mark.asyncio
async def test_command_roll_rejects_wrong_count():
    ar = make_bracket()
    ar.lobby.say = AsyncMock()
    await ar._dispatch_command("roll", ["Red"], "cli")
    assert ar.ranking is None


@pytest.mark.asyncio
async def test_command_order_picks_scheme():
    schemes = [OrderScheme("A"), OrderScheme("B", pick_first=1)]
    ar = make_bracket(schemes=schemes)
    ar.lobby.say = AsyncMock()
    await ar._dispatch_command("order", ["2"], "cli")
    assert ar.scheme is schemes[1]
    assert ar._order_done.is_set()


@pytest.mark.asyncio
async def test_command_order_rejects_out_of_range():
    schemes = [OrderScheme("A")]
    ar = make_bracket(schemes=schemes)
    ar.lobby.say = AsyncMock()
    await ar._dispatch_command("order", ["5"], "cli")
    assert ar.scheme is None


# ---------------------------------------------------------------- roll phase

def _async_none():
    async def _(*a, **kw): return None
    return _()


@pytest.mark.asyncio
async def test_roll_phase_auto_ranks_on_all_teams_rolled():
    import asyncio as _asyncio
    ar = make_bracket()
    ar.roll_timeout = 1
    ar.lobby.say = AsyncMock()
    ar.lobby.players = ["red1", "blue1"]  # Mock players present
    ar.mode = RefMode.AUTO  # Set mode to non-OFF
    # capture the registered handler
    handlers = []
    ar.lobby.channel = MagicMock()
    ar.lobby.channel.on = lambda ev, fn: handlers.append(fn)
    ar.lobby.channel.remove_listener = lambda ev, fn: None

    task = _asyncio.create_task(ar._run_roll_phase())
    await _asyncio.sleep(0.01)
    handler = handlers[0]
    handler(_fake_msg("BanchoBot", "red1 rolls 42 point(s)"))
    handler(_fake_msg("BanchoBot", "blue1 rolls 73 point(s)"))
    await task
    assert ar.ranking == [1, 0]  # blue rolled higher


@pytest.mark.asyncio
async def test_roll_phase_ignores_non_banchobot():
    import asyncio as _asyncio
    ar = make_bracket()
    ar.roll_timeout = 0.05  # short timeout
    ar.lobby.say = AsyncMock()
    ar.lobby.players = ["red1", "blue1"]  # Mock players present
    ar.mode = RefMode.AUTO  # Set mode to non-OFF
    handlers = []
    ar.lobby.channel = MagicMock()
    ar.lobby.channel.on = lambda ev, fn: handlers.append(fn)
    ar.lobby.channel.remove_listener = lambda ev, fn: None

    task = _asyncio.create_task(ar._run_roll_phase())
    await _asyncio.sleep(0.01)
    handler = handlers[0]
    handler(_fake_msg("red1", "red1 rolls 999 point(s)"))  # not BanchoBot
    await task
    # no rolls captured, fallback to default order
    assert ar.ranking == [0, 1]


@pytest.mark.asyncio
async def test_roll_phase_ignores_unknown_user():
    import asyncio as _asyncio
    ar = make_bracket()
    ar.roll_timeout = 0.05
    ar.lobby.say = AsyncMock()
    ar.lobby.players = ["red1", "blue1"]  # Mock players present
    ar.mode = RefMode.AUTO  # Set mode to non-OFF
    handlers = []
    ar.lobby.channel = MagicMock()
    ar.lobby.channel.on = lambda ev, fn: handlers.append(fn)
    ar.lobby.channel.remove_listener = lambda ev, fn: None

    task = _asyncio.create_task(ar._run_roll_phase())
    await _asyncio.sleep(0.01)
    handler = handlers[0]
    handler(_fake_msg("BanchoBot", "spectator rolls 42 point(s)"))
    await task
    assert ar.ranking == [0, 1]  # nobody on a team rolled


@pytest.mark.asyncio
async def test_roll_phase_first_roll_per_team_wins():
    import asyncio as _asyncio
    ar = make_bracket()
    ar.roll_timeout = 1
    ar.lobby.say = AsyncMock()
    # two-player red team
    ar.match.teams = (make_team("Red", "r1", "r2"), make_team("Blue", "b1"))
    ar._wins = [0, 0]
    ar.lobby.players = ["r1", "r2", "b1"]  # Mock players present
    ar.mode = RefMode.AUTO  # Set mode to non-OFF
    handlers = []
    ar.lobby.channel = MagicMock()
    ar.lobby.channel.on = lambda ev, fn: handlers.append(fn)
    ar.lobby.channel.remove_listener = lambda ev, fn: None

    task = _asyncio.create_task(ar._run_roll_phase())
    await _asyncio.sleep(0.01)
    handler = handlers[0]
    handler(_fake_msg("BanchoBot", "r1 rolls 10 point(s)"))
    handler(_fake_msg("BanchoBot", "r2 rolls 100 point(s)"))  # ignored (2nd for red)
    handler(_fake_msg("BanchoBot", "b1 rolls 50 point(s)"))
    await task
    assert ar._rolls == {0: 10, 1: 50}
    assert ar.ranking == [1, 0]


@pytest.mark.asyncio
async def test_roll_phase_released_by_override_command():
    import asyncio as _asyncio
    ar = make_bracket()
    ar.roll_timeout = 5
    ar.lobby.say = AsyncMock()
    ar.lobby.players = ["red1", "blue1"]  # Mock players present
    ar.mode = RefMode.AUTO  # Set mode to non-OFF
    ar.lobby.channel = MagicMock()
    ar.lobby.channel.on = lambda ev, fn: None
    ar.lobby.channel.remove_listener = lambda ev, fn: None

    task = _asyncio.create_task(ar._run_roll_phase())
    await _asyncio.sleep(0.01)
    await ar._dispatch_command("roll", ["Red", "Blue"], "cli")
    await task
    assert ar.ranking == [0, 1]



@pytest.mark.asyncio
async def test_pick_timeout_passes_to_other_team():
    """When pick timer expires, other team picks but original team keeps next pick."""
    import asyncio as _asyncio
    ar = make_bracket()
    ar.timers.pick = 0.05  # Short timeout
    ar.lobby.say = AsyncMock()
    ar.mode = RefMode.AUTO
    
    # Track which team was asked to pick
    pick_calls = []
    original_await = ar._await_map_choice
    
    async def mock_await_choice(team_idx, for_ban=False):
        pick_calls.append(team_idx)
        if len(pick_calls) == 1:
            # First call (team 0) - timeout
            await _asyncio.sleep(1)  # Will be interrupted by timeout
            return None
        else:
            # Second call (team 1) - pick immediately
            return 123456  # Some beatmap_id
    
    ar._await_map_choice = mock_await_choice
    
    # Team 0 should pick
    result = await ar.await_pick(0)
    
    # Verify timeout message was sent
    assert any("ran out of time" in str(call) for call in ar.lobby.say.call_args_list)
    # Verify team 1 was asked to pick after timeout
    assert pick_calls == [0, 1]
    # Verify pick count was decremented
    assert ar._pick_count == -1  # Started at 0, decremented to -1
    assert result == 123456

# ---------------------------------------------------------------- order phase

@pytest.mark.asyncio
async def test_order_phase_auto_selects_when_single():
    ar = make_bracket()
    ar.set_ranking([0, 1])
    await ar._run_order_phase()
    assert ar.scheme is ar.schemes[0]


@pytest.mark.asyncio
async def test_order_phase_waits_for_command():
    import asyncio as _asyncio
    schemes = [OrderScheme("A"), OrderScheme("B", pick_first=1)]
    ar = make_bracket(schemes=schemes)
    ar.set_ranking([1, 0])
    ar.lobby.say = AsyncMock()

    task = _asyncio.create_task(ar._run_order_phase())
    await _asyncio.sleep(0.01)
    assert ar.scheme is None
    await ar._dispatch_command("order", ["2"], "cli")
    await task
    assert ar.scheme is schemes[1]
