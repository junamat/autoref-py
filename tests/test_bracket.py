"""Tests for BracketAutoRef state machine."""
from unittest.mock import MagicMock

import pytest
import bancho

from autoref.bracket import BracketAutoRef, Phase
from autoref.enums import MapState, Step, WinCondition
from autoref.lobby import MatchResult, PlayerResult
from autoref.models import (
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
    ar = make_bracket(best_of=1, bans=1, protects=1)
    ar.set_ranking([0, 1])
    ar.commit_scheme(OrderScheme("s"))
    assert ar.next_step(None) == (0, Step.PROTECT)
    assert ar.next_step(None) == (1, Step.PROTECT)
    assert ar.next_step(None) == (0, Step.BAN)
    assert ar.next_step(None) == (1, Step.BAN)
    assert ar.next_step(None) == (0, Step.PICK)  # pick_first=0 + no prior map


def test_next_step_pick_alternates_on_loser():
    ar = make_bracket(best_of=3)
    ar.set_ranking([0, 1])
    ar.commit_scheme(OrderScheme("s", pick_first=0))
    t1, _ = ar.next_step(None)
    assert t1 == 0
    # simulate team 0 won
    ar._wins[0] = 1
    ar._last_map_winner = 0
    t2, _ = ar.next_step(None)
    assert t2 == 1   # loser picks next


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


def test_map_winner_ignores_failed_players():
    ar = make_bracket()
    result = MatchResult(scores=[
        PlayerResult("red1", 999_999, False),   # failed — excluded
        PlayerResult("blue1", 100_000, True),
    ])
    assert ar._map_winner(result) == 1


def test_map_winner_none_on_empty():
    ar = make_bracket()
    assert ar._map_winner(MatchResult(scores=[])) is None
    assert ar._map_winner(None) is None
