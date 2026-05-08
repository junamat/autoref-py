"""T48: mid-match disconnect → orphaned → reconnect w/ exp backoff (V29)."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from autoref.web.server import WebServer, _BACKOFF


def _make_ar_and_client(fail_count: int = 1):
    ar = MagicMock()
    ar.to_state_dict = MagicMock(return_value={})
    ar.from_state_dict = MagicMock()
    ar.add_state_hook = MagicMock()
    ar.lobby = MagicMock()
    ar.lobby.room_id = 42
    ar.lobby.add_message_hook = MagicMock()
    ar.lobby.register_reply_sink = MagicMock()

    runs: list[bool] = []

    async def _run_side(resume=False):
        runs.append(resume)
        if len(runs) <= fail_count:
            raise ConnectionError("bancho gone")

    ar.run = AsyncMock(side_effect=_run_side)
    ar._runs = runs  # expose for assertions

    client = MagicMock()
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    return ar, client


@pytest.mark.asyncio
async def test_disconnect_sets_orphaned_then_retries(tmp_path):
    """Disconnect during run → status orphaned → retry with resume=True → finished."""
    ar, client = _make_ar_and_client(fail_count=1)
    srv = WebServer(db_path=tmp_path / "t.db")

    sleep_delays: list[float] = []

    async def _fake_sleep(delay):
        sleep_delays.append(delay)

    with patch("autoref.factory.build_autoref", new=AsyncMock(return_value=(ar, client))), \
         patch("asyncio.sleep", side_effect=_fake_sleep):
        await srv._create_match(
            {"type": "bracket", "teams": [{"name": "A"}, {"name": "B"}]},
            match_id="m1",
        )
        await asyncio.wait_for(srv._tasks["m1"], timeout=3.0)

    row = srv.db._conn.execute(
        "SELECT status FROM live_matches WHERE match_id='m1'"
    ).fetchone()
    assert row[0] == "finished"

    assert ar.run.call_count == 2
    assert ar._runs == [False, True]
    assert sleep_delays and sleep_delays[0] == _BACKOFF[0]


@pytest.mark.asyncio
async def test_multiple_disconnects_follow_backoff_sequence(tmp_path):
    """N disconnects → backoff delays are _BACKOFF[0..N-1]."""
    fail_count = 3
    ar, client = _make_ar_and_client(fail_count=fail_count)
    srv = WebServer(db_path=tmp_path / "t.db")

    sleep_delays: list[float] = []

    async def _fake_sleep(delay):
        sleep_delays.append(delay)

    with patch("autoref.factory.build_autoref", new=AsyncMock(return_value=(ar, client))), \
         patch("asyncio.sleep", side_effect=_fake_sleep):
        await srv._create_match(
            {"type": "bracket", "teams": [{"name": "A"}, {"name": "B"}]},
            match_id="m2",
        )
        await asyncio.wait_for(srv._tasks["m2"], timeout=3.0)

    assert ar.run.call_count == fail_count + 1
    assert sleep_delays[:fail_count] == _BACKOFF[:fail_count]


@pytest.mark.asyncio
async def test_backoff_caps_at_max(tmp_path):
    """Beyond _BACKOFF length → delay stays at _BACKOFF[-1]."""
    fail_count = len(_BACKOFF) + 2
    ar, client = _make_ar_and_client(fail_count=fail_count)
    srv = WebServer(db_path=tmp_path / "t.db")

    sleep_delays: list[float] = []

    async def _fake_sleep(delay):
        sleep_delays.append(delay)

    with patch("autoref.factory.build_autoref", new=AsyncMock(return_value=(ar, client))), \
         patch("asyncio.sleep", side_effect=_fake_sleep):
        await srv._create_match(
            {"type": "bracket", "teams": [{"name": "A"}, {"name": "B"}]},
            match_id="m3",
        )
        await asyncio.wait_for(srv._tasks["m3"], timeout=3.0)

    assert all(d <= _BACKOFF[-1] for d in sleep_delays)
    assert sleep_delays[len(_BACKOFF) - 1] == _BACKOFF[-1]
    assert sleep_delays[-1] == _BACKOFF[-1]
