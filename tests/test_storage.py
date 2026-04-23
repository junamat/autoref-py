from unittest.mock import MagicMock

import pandas as pd
import pytest

from autoref.enums import Step, WinCondition
from autoref.models import Match, Pool, PlayableMap, Ruleset, Team
from autoref.storage import MatchDatabase


def make_ruleset() -> Ruleset:
    ruleset = MagicMock(spec=Ruleset)
    ruleset.vs = 2
    ruleset.gamemode = MagicMock()
    ruleset.gamemode.name_api = "osu"
    ruleset.win_condition = WinCondition.SCORE_V2
    return ruleset


def make_match_with_actions() -> Match:
    match = Match(
        make_ruleset(),
        Pool("pool", PlayableMap(1), PlayableMap(2)),
        MagicMock(return_value=(0, Step.PICK)),
        Team("Red"),
        Team("Blue"),
    )
    match.record_action(0, Step.BAN, 101)
    match.record_action(1, Step.BAN, 102)
    match.record_action(0, Step.PICK, 103)
    match.record_action(1, Step.PICK, 104)
    return match


@pytest.fixture
def db():
    return MatchDatabase(":memory:")


def test_save_match_returns_id(db):
    match = make_match_with_actions()
    match_id = db.save_match(match)
    assert match_id == 1
    assert match.match_id == 1


def test_save_match_sets_match_id_on_object(db):
    match = make_match_with_actions()
    db.save_match(match)
    assert match.match_id is not None


def test_save_multiple_matches_increments_id(db):
    id1 = db.save_match(make_match_with_actions())
    id2 = db.save_match(make_match_with_actions())
    assert id2 == id1 + 1


def test_get_match_history(db):
    db.save_match(make_match_with_actions())
    db.save_match(make_match_with_actions())
    history = db.get_match_history()
    assert len(history) == 2
    assert "match_id" in history.columns


def test_get_map_stats_counts_actions(db):
    match = make_match_with_actions()
    db.save_match(match)
    stats = db.get_map_stats()
    assert not stats.empty
    ban_rows = stats[stats["step"] == "BAN"]
    assert ban_rows["count"].sum() == 2


def test_get_team_stats_tracks_wins(db):
    match = make_match_with_actions()
    db.save_match(match, winner_team_index=0)
    stats = db.get_team_stats()
    red = stats[stats["team_name"] == "Red"].iloc[0]
    blue = stats[stats["team_name"] == "Blue"].iloc[0]
    assert red["wins"] == 1
    assert blue["wins"] == 0


def test_get_team_stats_tracks_matches_played(db):
    db.save_match(make_match_with_actions(), winner_team_index=0)
    db.save_match(make_match_with_actions(), winner_team_index=1)
    stats = db.get_team_stats()
    red = stats[stats["team_name"] == "Red"].iloc[0]
    assert red["matches_played"] == 2


def test_save_match_without_actions(db):
    match = Match(
        make_ruleset(),
        Pool("pool"),
        MagicMock(),
        Team("Red"),
        Team("Blue"),
    )
    match_id = db.save_match(match)
    assert match_id is not None
    stats = db.get_map_stats()
    assert stats.empty
