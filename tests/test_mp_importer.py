"""Tests for mp_importer module."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from autoref.core.db import MatchDatabase
from autoref.core.mp_importer import (
    ImportedGame,
    ImportedMatch,
    fetch_mp_match,
    save_imported_match,
)
from autoref.core.mp_link import MpLink


@dataclass
class MockMod:
    acronym: str


@dataclass
class MockRank:
    value: str


@dataclass
class MockScore:
    user_id: int
    score: int
    accuracy: float
    max_combo: int
    passed: bool
    perfect: bool
    mods: list[MockMod]
    rank: MockRank
    match: Any = None


@dataclass
class MockGame:
    id: int
    beatmap_id: int
    start_time: str
    end_time: str | None
    scores: list[MockScore]
    team_type: str = "team-vs"


@dataclass
class MockEvent:
    game: MockGame | None


@dataclass
class MockUser:
    id: int
    username: str


@dataclass
class MockMatchInfo:
    name: str
    type: str
    start_time: str
    end_time: str


@dataclass
class MockMatchResponse:
    match: MockMatchInfo
    users: list[MockUser]
    events: list[MockEvent]


def make_mock_score(user_id: int, score: int = 800000, team: int | None = None) -> MockScore:
    match_obj = None
    if team is not None:
        match_obj = type("MatchTeam", (), {"team": team})()
    return MockScore(
        user_id=user_id,
        score=score,
        accuracy=0.95,
        max_combo=500,
        passed=True,
        perfect=False,
        mods=[MockMod("HD")],
        rank=MockRank("S"),
        match=match_obj,
    )


def make_mock_response(
    match_id: int = 123456,
    match_name: str = "Test Match",
    match_type: str = "TeamVs",
    users: list[tuple[int, str]] | None = None,
    games: list[tuple[int, list[MockScore]]] | None = None,
) -> MockMatchResponse:
    if users is None:
        users = [(1001, "Player1"), (1002, "Player2"), (1003, "Player3"), (1004, "Player4")]
    if games is None:
        games = [
            (5001, [
                make_mock_score(1001, 800000, team=0),
                make_mock_score(1002, 750000, team=0),
                make_mock_score(1003, 780000, team=1),
                make_mock_score(1004, 720000, team=1),
            ]),
            (5002, [
                make_mock_score(1001, 850000, team=0),
                make_mock_score(1002, 820000, team=0),
                make_mock_score(1003, 900000, team=1),
                make_mock_score(1004, 880000, team=1),
            ]),
        ]

    # Convert match_type to team_type format used in API
    team_type = "team-vs" if match_type == "TeamVs" else "head-to-head"

    events = []
    for i, (bid, scores) in enumerate(games):
        game = MockGame(
            id=1000 + i,
            beatmap_id=bid,
            start_time="2024-01-01T12:00:00Z",
            end_time="2024-01-01T12:05:00Z",
            scores=scores,
            team_type=team_type,
        )
        events.append(MockEvent(game=game))

    return MockMatchResponse(
        match=MockMatchInfo(
            name=match_name,
            type=match_type,
            start_time="2024-01-01T12:00:00Z",
            end_time="2024-01-01T14:00:00Z",
        ),
        users=[MockUser(uid, uname) for uid, uname in users],
        events=events,
    )


class TestFetchMpMatch:
    @pytest.mark.asyncio
    async def test_fetch_team_vs_match(self):
        client = AsyncMock()
        client.get_multiplayer_match.return_value = make_mock_response()

        result = await fetch_mp_match(client, MpLink(123456, None))

        assert result.match_id == 123456
        assert result.name == "Test Match"
        assert result.match_type == "teamvs"
        assert len(result.games) == 2
        assert len(result.users) == 4
        assert result.users[1001] == "Player1"

    @pytest.mark.asyncio
    async def test_fetch_head_to_head_match(self):
        client = AsyncMock()
        client.get_multiplayer_match.return_value = make_mock_response(
            match_type="HeadToHead",
            games=[
                (5001, [
                    make_mock_score(1001, 800000),
                    make_mock_score(1002, 750000),
                ]),
            ],
        )

        result = await fetch_mp_match(client, MpLink(123456, None))

        assert result.match_type == "headtohead"
        assert len(result.games) == 1

    @pytest.mark.asyncio
    async def test_fetch_skips_incomplete_games(self):
        client = AsyncMock()
        incomplete_game = MockGame(
            id=1000,
            beatmap_id=5001,
            start_time="2024-01-01T12:00:00Z",
            end_time=None,
            scores=[],
        )
        response = MockMatchResponse(
            match=MockMatchInfo("Test", "TeamVs", "", ""),
            users=[MockUser(1001, "P1")],
            events=[MockEvent(game=incomplete_game)],
        )
        client.get_multiplayer_match.return_value = response

        result = await fetch_mp_match(client, MpLink(123456, None))

        assert len(result.games) == 0


class TestSaveImportedMatch:
    def test_save_match_each_player_is_team(self, tmp_path):
        db = MatchDatabase(tmp_path / "test.db")
        imported = ImportedMatch(
            match_id=123456,
            name="Test Match",
            match_type="TeamVs",
            users={1001: "Player1", 1002: "Player2", 1003: "Player3", 1004: "Player4"},
            games=[
                ImportedGame(
                    beatmap_id=5001,
                    scores=[
                        {"user_id": 1001, "username": "Player1", "score": 800000,
                         "accuracy": 0.95, "max_combo": 500, "passed": True,
                         "perfect": False, "mods": ["HD"], "rank": "S", "team": 0},
                        {"user_id": 1002, "username": "Player2", "score": 750000,
                         "accuracy": 0.93, "max_combo": 450, "passed": True,
                         "perfect": False, "mods": ["HD"], "rank": "A", "team": 0},
                        {"user_id": 1003, "username": "Player3", "score": 780000,
                         "accuracy": 0.94, "max_combo": 480, "passed": True,
                         "perfect": False, "mods": ["HD"], "rank": "A", "team": 1},
                        {"user_id": 1004, "username": "Player4", "score": 720000,
                         "accuracy": 0.91, "max_combo": 400, "passed": True,
                         "perfect": False, "mods": ["HD"], "rank": "B", "team": 1},
                    ],
                ),
            ],
        )

        mid = save_imported_match(db, imported, pool_id="test_pool", round_name="ro16")

        assert mid is not None
        assert mid > 0

        scores = db.get_all_scores(pool_id="test_pool", round_name="ro16")
        assert len(scores) == 4

        # Each player is their own team
        teams = db._conn.execute(
            "SELECT team_name FROM match_teams WHERE match_id = ? ORDER BY team_index", (mid,)
        ).fetchall()
        assert len(teams) == 4
        assert teams[0][0] == "Player1"
        assert teams[1][0] == "Player2"
        assert teams[2][0] == "Player3"
        assert teams[3][0] == "Player4"

        db.close()

    def test_save_head_to_head_match(self, tmp_path):
        db = MatchDatabase(tmp_path / "test.db")
        imported = ImportedMatch(
            match_id=123456,
            name="Test Match",
            match_type="HeadToHead",
            users={1001: "Player1", 1002: "Player2"},
            games=[
                ImportedGame(
                    beatmap_id=5001,
                    scores=[
                        {"user_id": 1001, "username": "Player1", "score": 800000,
                         "accuracy": 0.95, "max_combo": 500, "passed": True,
                         "perfect": False, "mods": ["HD"], "rank": "S", "team": None},
                        {"user_id": 1002, "username": "Player2", "score": 750000,
                         "accuracy": 0.93, "max_combo": 450, "passed": True,
                         "perfect": False, "mods": ["HD"], "rank": "A", "team": None},
                    ],
                ),
            ],
        )

        mid = save_imported_match(db, imported)

        scores = db.get_all_scores()
        assert len(scores) == 2

        teams = db._conn.execute(
            "SELECT team_name FROM match_teams WHERE match_id = ? ORDER BY team_index", (mid,)
        ).fetchall()
        assert len(teams) == 2

        db.close()

    def test_save_multiple_games(self, tmp_path):
        db = MatchDatabase(tmp_path / "test.db")
        imported = ImportedMatch(
            match_id=123456,
            name="Test Match",
            match_type="TeamVs",
            users={1001: "P1", 1002: "P2"},
            games=[
                ImportedGame(beatmap_id=5001, scores=[
                    {"user_id": 1001, "username": "P1", "score": 800000,
                     "accuracy": 0.95, "max_combo": 500, "passed": True,
                     "perfect": False, "mods": [], "rank": "S", "team": 0},
                    {"user_id": 1002, "username": "P2", "score": 750000,
                     "accuracy": 0.93, "max_combo": 450, "passed": True,
                     "perfect": False, "mods": [], "rank": "A", "team": 1},
                ]),
                ImportedGame(beatmap_id=5002, scores=[
                    {"user_id": 1001, "username": "P1", "score": 850000,
                     "accuracy": 0.96, "max_combo": 520, "passed": True,
                     "perfect": False, "mods": [], "rank": "S", "team": 0},
                    {"user_id": 1002, "username": "P2", "score": 900000,
                     "accuracy": 0.97, "max_combo": 550, "passed": True,
                     "perfect": False, "mods": [], "rank": "S", "team": 1},
                ]),
            ],
        )

        save_imported_match(db, imported)

        scores = db.get_all_scores()
        assert len(scores) == 4

        turns = scores["turn"].unique()
        assert len(turns) == 2
        assert set(turns) == {1, 2}

        db.close()


class TestSaveImportedMatchWithPP:
    @pytest.mark.asyncio
    async def test_pp_calculated_during_import(self, tmp_path):
        """Test that PP values are calculated when importing with save_imported_match_with_pp."""
        db = MatchDatabase(tmp_path / "test.db")
        imported = ImportedMatch(
            match_id=123456,
            name="Test Match",
            match_type="HeadToHead",
            users={1001: "Player1", 1002: "Player2"},
            games=[
                ImportedGame(
                    beatmap_id=5670811,  # Valid beatmap ID
                    scores=[
                        {"user_id": 1001, "username": "Player1", "score": 900000,
                         "accuracy": 98.5, "max_combo": 100, "passed": True,
                         "perfect": False, "mods": ["HD"], "rank": "S", "team": None},
                        {"user_id": 1002, "username": "Player2", "score": 850000,
                         "accuracy": 95.0, "max_combo": 90, "passed": True,
                         "perfect": False, "mods": ["HD"], "rank": "A", "team": None},
                    ],
                ),
            ],
        )

        from autoref.core.mp_importer import save_imported_match_with_pp
        mid = await save_imported_match_with_pp(db, imported, pool_id="test_pool", round_name="test")

        assert mid is not None

        # Check that PP values were calculated
        scores = db.get_all_scores(pool_id="test_pool", round_name="test")
        assert len(scores) == 2
        assert "pp" in scores.columns

        # PP should be calculated for at least one score (may fail for some due to network issues)
        pp_values = scores["pp"].dropna()
        assert len(pp_values) > 0, "At least one PP value should be calculated"

        db.close()
