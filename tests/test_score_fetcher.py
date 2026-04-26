"""Tests for ScoreFetcher polling logic and Match.game_scores buffer."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from autoref.core.score_fetcher import ScoreFetcher


def _mock_score(user_id, score, accuracy=0.95, max_combo=500, passed=True,
                perfect=False, mods=(), rank="A"):
    return SimpleNamespace(
        user_id=user_id, score=score, accuracy=accuracy,
        max_combo=max_combo, passed=passed, perfect=perfect,
        mods=[SimpleNamespace(acronym=m) for m in mods],
        rank=SimpleNamespace(value=rank),
    )


def _mock_game(game_id, beatmap_id, scores, end_time="now"):
    return SimpleNamespace(
        id=game_id, beatmap_id=beatmap_id, scores=scores, end_time=end_time,
    )


def _mock_event(game):
    return SimpleNamespace(game=game)


def _resp(*games):
    return SimpleNamespace(events=[_mock_event(g) for g in games])


@pytest.mark.asyncio
async def test_fetch_returns_enriched_scores(monkeypatch):
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    client = SimpleNamespace(get_multiplayer_match=AsyncMock(return_value=_resp(
        _mock_game(1, 42, [_mock_score(100, 800_000, mods=("HD",))]),
    )))
    f = ScoreFetcher(client, initial_delay=0, max_delay=0, timeout=10)
    scores = await f.fetch_for_game(123, 42)
    assert scores is not None
    assert scores[0]["user_id"] == 100
    assert scores[0]["score"] == 800_000
    assert scores[0]["mods"] == ["HD"]


@pytest.mark.asyncio
async def test_fetch_skips_unfinished_game(monkeypatch):
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    # First call: game exists but end_time is None → keep polling
    # Second call: game finished
    client = SimpleNamespace(get_multiplayer_match=AsyncMock(side_effect=[
        _resp(_mock_game(1, 42, [_mock_score(100, 1)], end_time=None)),
        _resp(_mock_game(1, 42, [_mock_score(100, 1)], end_time="now")),
    ]))
    f = ScoreFetcher(client, initial_delay=0, max_delay=0, timeout=10)
    scores = await f.fetch_for_game(123, 42)
    assert scores is not None
    assert client.get_multiplayer_match.await_count == 2


@pytest.mark.asyncio
async def test_fetch_filters_by_beatmap_id(monkeypatch):
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    client = SimpleNamespace(get_multiplayer_match=AsyncMock(return_value=_resp(
        _mock_game(1, 7, [_mock_score(100, 1)]),
        _mock_game(2, 9, [_mock_score(100, 2)]),
    )))
    f = ScoreFetcher(client, initial_delay=0, max_delay=0, timeout=10)
    scores = await f.fetch_for_game(123, 9)
    assert scores[0]["score"] == 2


@pytest.mark.asyncio
async def test_fetch_skips_already_seen_game(monkeypatch):
    """Same fetcher reused across maps must not re-return the previous game."""
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    # Both calls return the same game id 5 — second call should time out (None).
    resp = _resp(_mock_game(5, 42, [_mock_score(100, 1)]))
    client = SimpleNamespace(get_multiplayer_match=AsyncMock(return_value=resp))
    f = ScoreFetcher(client, initial_delay=0, max_delay=0, timeout=0.05)
    first = await f.fetch_for_game(123, 42)
    assert first is not None
    second = await f.fetch_for_game(123, 42)
    assert second is None


@pytest.mark.asyncio
async def test_fetch_timeout_returns_none(monkeypatch):
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    client = SimpleNamespace(get_multiplayer_match=AsyncMock(return_value=_resp()))
    f = ScoreFetcher(client, initial_delay=0, max_delay=0, timeout=0.05)
    assert await f.fetch_for_game(123, 42) is None


@pytest.mark.asyncio
async def test_aclose_calls_client_aclose():
    aclose = AsyncMock()
    client = SimpleNamespace(aclose=aclose)
    f = ScoreFetcher(client)
    await f.aclose()
    aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_aclose_noop_when_client_has_no_aclose():
    client = SimpleNamespace()  # no aclose
    f = ScoreFetcher(client)
    await f.aclose()  # must not raise


@pytest.mark.asyncio
async def test_fetch_swallows_api_errors_and_retries(monkeypatch):
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    # First call raises, second succeeds.
    client = SimpleNamespace(get_multiplayer_match=AsyncMock(side_effect=[
        RuntimeError("boom"),
        _resp(_mock_game(1, 42, [_mock_score(100, 1)])),
    ]))
    f = ScoreFetcher(client, initial_delay=0, max_delay=0, timeout=10)
    scores = await f.fetch_for_game(123, 42)
    assert scores is not None
