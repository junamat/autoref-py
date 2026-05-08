"""T45: to_state_dict / from_state_dict round-trip for all controllers."""
from unittest.mock import AsyncMock, MagicMock
import pandas as pd
import pytest
import bancho

from autoref.core.enums import RefMode, Step, WinCondition
from autoref.core.models import Match, OrderScheme, PlayableMap, Pool, Ruleset, Team, Timers
from autoref.controllers.bracket import BracketAutoRef, Phase
from autoref.controllers.qualifiers import QualifiersAutoRef
from autoref.controllers.voted import VotedQualifiersAutoRef


# ------------------------------------------------------------------ helpers

def _ruleset(*, best_of=5, bans=1, protects=1):
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
    r.schemes = None
    r.wins_needed = best_of // 2 + 1
    r.bans_for = lambda i: bans
    r.protects_for = lambda i: protects
    return r


def _pool():
    maps = [PlayableMap(i, name=f"M{i}") for i in range(1, 7)]
    maps.append(PlayableMap(99, name="TB", is_tiebreaker=True))
    return Pool("p", *maps)


def _mock_lobby():
    lobby = MagicMock()
    lobby.room_id = 12345
    lobby.create = AsyncMock(return_value=12345)
    lobby.attach = AsyncMock(return_value=12345)
    lobby.set_room = AsyncMock()
    lobby.set_mods = AsyncMock()
    lobby.invite = AsyncMock()
    lobby.close = AsyncMock()
    lobby.say = AsyncMock()
    lobby.players = set()
    return lobby


def _make_bracket():
    match = Match(_ruleset(), _pool(), MagicMock(), Team("A"), Team("B"))
    ar = BracketAutoRef(
        MagicMock(spec=bancho.BanchoClient), match, "Room",
        mode=RefMode.OFF, timers=Timers(closing=0),
    )
    ar.lobby = _mock_lobby()
    return ar


def _make_qualifiers():
    pool = Pool("p", *[PlayableMap(i, name=f"M{i}") for i in range(1, 4)])
    r = MagicMock(spec=Ruleset)
    r.vs = 1; r.gamemode = MagicMock(); r.gamemode.value = 0
    r.win_condition = WinCondition.SCORE_V2; r.enforced_mods = ""
    r.team_mode = 0; r.best_of = 1
    match = Match(r, pool, MagicMock(), Team("A"))
    ar = QualifiersAutoRef(
        MagicMock(spec=bancho.BanchoClient), match, "Room",
        runs=2, mode=RefMode.OFF, timers=Timers(closing=0),
    )
    ar.lobby = _mock_lobby()
    ar._beatmap_cache = MagicMock()
    ar._beatmap_cache.get = MagicMock(return_value=None)
    return ar


def _make_voted():
    pool = Pool("p", *[PlayableMap(i, name=f"M{i}") for i in range(1, 4)])
    r = MagicMock(spec=Ruleset)
    r.vs = 1; r.gamemode = MagicMock(); r.gamemode.value = 0
    r.win_condition = WinCondition.SCORE_V2; r.enforced_mods = ""
    r.team_mode = 0; r.best_of = 1
    match = Match(r, pool, MagicMock(), Team("A"))
    ar = VotedQualifiersAutoRef(
        MagicMock(spec=bancho.BanchoClient), match, "Room",
        runs=2, mode=RefMode.OFF, timers=Timers(closing=0), seed=42,
    )
    ar.lobby = _mock_lobby()
    ar._beatmap_cache = MagicMock()
    ar._beatmap_cache.get = MagicMock(return_value=None)
    return ar


# ------------------------------------------------------------------ V30: DataFrame round-trip

def test_df_to_records_enum_coercion():
    import pandas as pd
    from autoref.core.ref.base import AutoRef
    df = pd.DataFrame([{"step": Step.PICK, "beatmap_id": 1, "turn": 0, "team_index": 0,
                        "timestamp": "2024-01-01T00:00:00"}])
    records = AutoRef._df_to_records(df)
    assert records[0]["step"] == "PICK"


def test_df_round_trip_cell_exact():
    from autoref.core.ref.base import AutoRef
    import pandas as pd
    df = pd.DataFrame([
        {"step": "PICK", "beatmap_id": 5, "turn": 1, "team_index": 0, "timestamp": "2024-01-01T00:00:00"},
        {"step": "BAN",  "beatmap_id": 3, "turn": 0, "team_index": 1, "timestamp": "2024-01-01T00:00:01"},
    ])
    records = AutoRef._df_to_records(df)
    df2 = AutoRef._records_to_df(records)
    assert list(df2["step"]) == ["PICK", "BAN"]
    assert list(df2["beatmap_id"]) == [5, 3]


# ------------------------------------------------------------------ V22: BracketAutoRef

def test_bracket_state_round_trip():
    ar = _make_bracket()
    ar.ranking = [0, 1]
    ar.commit_scheme(ar.schemes[0])
    ar._wins = [2, 1]
    ar._pick_count = 3
    ar._ban_cursor = 1
    ar._protect_cursor = 1

    d = ar.to_state_dict()
    assert d["phase"] == ar.phase.name
    assert d["wins"] == [2, 1]
    # bancho_lobby_id comes from lobby.room_id
    assert d["bancho_lobby_id"] == 12345

    ar2 = _make_bracket()
    ar2.from_state_dict(d)
    assert ar2.phase == ar.phase
    assert ar2._wins == [2, 1]
    assert ar2._pick_count == 3
    assert ar2._ban_cursor == 1
    assert ar2._bancho_lobby_id == 12345


def test_bracket_match_status_preserved():
    import pandas as pd
    ar = _make_bracket()
    ar.match.match_status = pd.DataFrame([
        {"step": "PICK", "beatmap_id": 1, "turn": 0, "team_index": 0, "timestamp": "2024-01-01"},
    ])
    ar.ranking = [0, 1]
    ar.commit_scheme(ar.schemes[0])

    d = ar.to_state_dict()
    ar2 = _make_bracket()
    ar2.from_state_dict(d)
    assert not ar2.match.match_status.empty
    assert ar2.match.match_status.iloc[0]["beatmap_id"] == 1


# ------------------------------------------------------------------ V24: QualifiersAutoRef

def test_qualifiers_state_round_trip():
    ar = _make_qualifiers()
    ar._map_index = 2
    ar._run_index = 1

    d = ar.to_state_dict()
    assert d["map_index"] == 2
    assert d["run_index"] == 1
    # bancho_lobby_id comes from lobby.room_id (12345 from mock)
    assert d["bancho_lobby_id"] == 12345

    ar2 = _make_qualifiers()
    ar2.from_state_dict(d)
    assert ar2._map_index == 2
    assert ar2._run_index == 1
    assert ar2._bancho_lobby_id == 12345


# ------------------------------------------------------------------ V25: VotedQualifiersAutoRef

def test_voted_state_round_trip():
    ar = _make_voted()
    ar._play_counts = {1: 1, 2: 0, 3: 2}
    ar._run_index = 1
    ar._maps_in_run = 2
    ar._active_players = {"alice", "bob"}
    ar._quit_players = {"charlie"}
    ar._vote_log = [{"picker": "alice", "map": "M1", "via": "chosen", "passers": []}]

    d = ar.to_state_dict()

    ar2 = _make_voted()
    ar2.from_state_dict(d)
    assert ar2._play_counts == {1: 1, 2: 0, 3: 2}
    assert ar2._run_index == 1
    assert ar2._maps_in_run == 2
    assert ar2._active_players == {"alice", "bob"}
    assert ar2._quit_players == {"charlie"}
    assert ar2._vote_log[0]["map"] == "M1"
    assert ar2._seed == ar._seed
    assert ar2._bancho_lobby_id == 12345
