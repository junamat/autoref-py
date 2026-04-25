"""Tests for changes: map state enforcement, _map_winner, Command dataclass."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from autoref.core.base import (
    Command, _find_map_by_input, _find_map_by_input_pick, _find_map,
)
from autoref.core.enums import MapState, Step, WinCondition
from autoref.core.lobby import MatchResult, PlayerResult
from autoref.core.models import Match, PlayableMap, Pool, Ruleset, Team, OrderScheme
from autoref.controllers.bracket import BracketAutoRef


# ── helpers ──────────────────────────────────────────────────────────────────

def _player(name):
    p = MagicMock()
    p.username = name
    return p


def make_team(name, *players):
    t = Team(name)
    t.players = [_player(p) for p in players]
    return t


def make_ruleset(**kw):
    r = MagicMock(spec=Ruleset)
    r.vs = 1
    r.gamemode = MagicMock(); r.gamemode.value = 0
    r.win_condition = WinCondition.SCORE_V2
    r.enforced_mods = ""
    r.team_mode = 0
    r.best_of = kw.get("best_of", 1)
    r.bans_per_team = kw.get("bans", 0)
    r.protects_per_team = kw.get("protects", 0)
    r.schemes = None
    r.wins_needed = r.best_of // 2 + 1
    r.bans_for = lambda i: r.bans_per_team
    r.protects_for = lambda i: r.protects_per_team
    return r


def make_match_with_maps(*names):
    maps = [PlayableMap(i + 1, name=n) for i, n in enumerate(names)]
    pool = Pool("p", *maps)
    match = Match(make_ruleset(), pool, MagicMock(), make_team("R", "r1"), make_team("B", "b1"))
    return match, maps


def make_bracket(**kw):
    import bancho
    bans = kw.pop("bans", 0)
    protects = kw.pop("protects", 0)
    best_of = kw.pop("best_of", 1)
    names = kw.pop("maps", ["M1", "M2", "M3", "M4", "M5", "M6"])
    with_tb = kw.pop("with_tb", False)
    if with_tb:
        names = list(names) + ["TB"]
    maps = [PlayableMap(i + 1, name=n, is_tiebreaker=(n == "TB")) for i, n in enumerate(names)]
    pool = Pool("p", *maps)
    r = make_ruleset(best_of=best_of, bans=bans, protects=protects)
    teams = (make_team("Red", "r1"), make_team("Blue", "b1"))
    match = Match(r, pool, MagicMock(), *teams)
    ar = BracketAutoRef(MagicMock(spec=bancho.BanchoClient), match, "Room",
                        schemes=[OrderScheme("default")])
    ar.lobby = MagicMock()
    ar.lobby.say = AsyncMock()
    ar.set_ranking([0, 1])
    ar.commit_scheme(OrderScheme("default"))
    return ar, maps


# ── _find_map_by_input (ban path: PICKABLE only) ──────────────────────────────

def test_ban_finds_pickable():
    match, maps = make_match_with_maps("NM1", "NM2")
    assert _find_map_by_input(match, "NM1") is maps[0]

def test_ban_rejects_protected():
    match, maps = make_match_with_maps("NM1")
    maps[0].state = MapState.PROTECTED
    assert _find_map_by_input(match, "NM1") is None

def test_ban_rejects_banned():
    match, maps = make_match_with_maps("NM1")
    maps[0].state = MapState.BANNED
    assert _find_map_by_input(match, "NM1") is None

def test_ban_rejects_played():
    match, maps = make_match_with_maps("NM1")
    maps[0].state = MapState.PLAYED
    assert _find_map_by_input(match, "NM1") is None

def test_ban_rejects_disallowed():
    match, maps = make_match_with_maps("NM1")
    maps[0].state = MapState.DISALLOWED
    assert _find_map_by_input(match, "NM1") is None


# ── _find_map_by_input_pick (pick path: PICKABLE + PROTECTED) ────────────────

def test_pick_finds_pickable():
    match, maps = make_match_with_maps("NM1")
    assert _find_map_by_input_pick(match, "NM1") is maps[0]

def test_pick_finds_protected():
    match, maps = make_match_with_maps("NM1")
    maps[0].state = MapState.PROTECTED
    assert _find_map_by_input_pick(match, "NM1") is maps[0]

def test_pick_rejects_banned():
    match, maps = make_match_with_maps("NM1")
    maps[0].state = MapState.BANNED
    assert _find_map_by_input_pick(match, "NM1") is None

def test_pick_rejects_played():
    match, maps = make_match_with_maps("NM1")
    maps[0].state = MapState.PLAYED
    assert _find_map_by_input_pick(match, "NM1") is None


# ── MapState.PLAYED set after handle_pick ────────────────────────────────────

@pytest.mark.asyncio
async def test_handle_pick_marks_map_played():
    ar, maps = make_bracket()
    ar.lobby.set_map = AsyncMock()
    ar.lobby.timer = AsyncMock()
    ar.lobby.wait_for_all_ready = AsyncMock()
    ar.lobby.wait_for_timer = AsyncMock()
    ar.lobby.start = AsyncMock()
    ar.lobby.wait_for_match_end = AsyncMock(return_value=MatchResult())
    await ar.handle_pick(0, maps[0].beatmap_id)
    assert maps[0].state == MapState.PLAYED

@pytest.mark.asyncio
async def test_played_map_not_pickable_again():
    ar, maps = make_bracket()
    ar.lobby.set_map = AsyncMock()
    ar.lobby.timer = AsyncMock()
    ar.lobby.wait_for_all_ready = AsyncMock()
    ar.lobby.wait_for_timer = AsyncMock()
    ar.lobby.start = AsyncMock()
    ar.lobby.wait_for_match_end = AsyncMock(return_value=MatchResult())
    await ar.handle_pick(0, maps[0].beatmap_id)
    # now it's PLAYED — neither ban nor pick path should find it
    assert _find_map_by_input(ar.match, maps[0].name) is None
    assert _find_map_by_input_pick(ar.match, maps[0].name) is None

@pytest.mark.asyncio
async def test_undo_resets_played_to_pickable():
    ar, maps = make_bracket()
    ar.lobby.set_map = AsyncMock()
    ar.lobby.timer = AsyncMock()
    ar.lobby.wait_for_all_ready = AsyncMock()
    ar.lobby.wait_for_timer = AsyncMock()
    ar.lobby.start = AsyncMock()
    ar.lobby.wait_for_match_end = AsyncMock(return_value=MatchResult())
    await ar.handle_pick(0, maps[0].beatmap_id)
    assert maps[0].state == MapState.PLAYED
    await ar._undo_last_action()
    assert maps[0].state == MapState.PICKABLE


# ── _map_winner ───────────────────────────────────────────────────────────────

def test_map_winner_counts_failed_scores():
    """Failed players' scores still count toward team total."""
    ar, _ = make_bracket()
    result = MatchResult(scores=[
        PlayerResult("r1", 800_000, False),   # failed but score counts
        PlayerResult("b1", 600_000, True),
    ])
    assert ar._map_winner(result) == 0  # red wins despite failing

def test_map_winner_both_zero_is_tie():
    ar, _ = make_bracket()
    result = MatchResult(scores=[
        PlayerResult("r1", 0, False),
        PlayerResult("b1", 0, False),
    ])
    assert ar._map_winner(result) is None

def test_map_winner_one_team_zero_other_nonzero():
    """A team with 0 score loses to a team with any score."""
    ar, _ = make_bracket()
    result = MatchResult(scores=[
        PlayerResult("r1", 0, False),
        PlayerResult("b1", 1, True),
    ])
    assert ar._map_winner(result) == 1

def test_map_winner_unknown_player_ignored():
    ar, _ = make_bracket()
    result = MatchResult(scores=[
        PlayerResult("spectator", 999_999, True),  # not on any team
        PlayerResult("b1", 100, True),
    ])
    assert ar._map_winner(result) == 1

def test_map_winner_multi_player_teams():
    ar, _ = make_bracket()
    ar.match.teams = (make_team("Red", "r1", "r2"), make_team("Blue", "b1", "b2"))
    result = MatchResult(scores=[
        PlayerResult("r1", 300_000, True),
        PlayerResult("r2", 300_000, True),   # red total: 600k
        PlayerResult("b1", 400_000, True),
        PlayerResult("b2", 300_000, True),   # blue total: 700k
    ])
    assert ar._map_winner(result) == 1


# ── Command dataclass ─────────────────────────────────────────────────────────

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
    assert not cmd.to_dict()["label"].startswith(">")
    assert cmd.to_dict()["label"].startswith("panic")

def test_command_usage_in_label():
    cmd = Command("next", usage="<map>")
    assert "<map>" in cmd.to_dict()["label"]

def test_command_bracket_only_flag():
    cmd = Command("fp", bracket_only=True)
    assert cmd.to_dict()["bracket_only"] is True

def test_commands_registry_not_empty():
    from autoref.core.base import COMMANDS
    assert len(COMMANDS) > 0
    # every command has a name and section
    for c in COMMANDS:
        assert c.name
        assert c.section
        assert c.scope in ("ref", "anyone")

def test_commands_registry_has_panic_noprefix():
    from autoref.core.base import COMMANDS
    panic = next(c for c in COMMANDS if c.name == "panic")
    assert panic.noprefix is True
    assert panic.scope == "anyone"

def test_commands_registry_bracket_only_filtered():
    from autoref.core.base import COMMANDS
    bracket_cmds = [c for c in COMMANDS if c.bracket_only]
    assert len(bracket_cmds) > 0
    non_bracket = [c for c in COMMANDS if not c.bracket_only]
    assert len(non_bracket) > 0
