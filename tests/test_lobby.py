"""Tests for Lobby wrapping BanchoLobby."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import bancho
from autoref.lobby import Lobby, MatchResult, PlayerResult


def make_lobby() -> tuple[Lobby, MagicMock]:
    """Return a Lobby with a mock BanchoClient and a pre-attached mock BanchoLobby."""
    client = MagicMock(spec=bancho.BanchoClient)
    lobby = Lobby(client)

    mock_bl = MagicMock(spec=bancho.BanchoLobby)
    mock_bl.id = 42
    mock_bl.channel = MagicMock()
    mock_bl.channel.send_message = AsyncMock()
    mock_bl.on = MagicMock()

    # Patch all !mp command coroutines
    for method in (
        "close_lobby", "set_map", "set_mods", "set_settings", "set_name",
        "set_password", "clear_password", "invite_player", "kick_player",
        "move_player", "change_team", "add_ref", "start_match", "abort_match",
        "start_timer", "abort_timer",
    ):
        setattr(mock_bl, method, AsyncMock())

    lobby._lobby = mock_bl
    return lobby, mock_bl


# ------------------------------------------------------------------ create

@pytest.mark.asyncio
async def test_create_uses_make_lobby():
    client = MagicMock(spec=bancho.BanchoClient)
    mock_bl = MagicMock(spec=bancho.BanchoLobby)
    mock_bl.id = 99
    mock_bl.on = MagicMock()
    mock_bl.channel = MagicMock()
    client.make_lobby = AsyncMock(return_value=mock_bl)

    lobby = Lobby(client)
    room_id = await lobby.create("Test Room")

    client.make_lobby.assert_called_once_with("Test Room")
    assert room_id == 99
    assert lobby._lobby is mock_bl


@pytest.mark.asyncio
async def test_create_registers_event_handlers():
    client = MagicMock(spec=bancho.BanchoClient)
    mock_bl = MagicMock(spec=bancho.BanchoLobby)
    mock_bl.id = 1
    mock_bl.on = MagicMock()
    mock_bl.channel = MagicMock()
    client.make_lobby = AsyncMock(return_value=mock_bl)

    lobby = Lobby(client)
    await lobby.create("Room")

    registered_events = {call.args[0] for call in mock_bl.on.call_args_list}
    assert registered_events >= {"playerJoined", "playerLeft", "matchStarted",
                                  "playerFinished", "matchFinished", "allPlayersReady", "timerEnded"}


# ------------------------------------------------------------------ room settings

@pytest.mark.asyncio
async def test_set_map():
    lobby, bl = make_lobby()
    await lobby.set_map(111, 0)
    bl.set_map.assert_called_once_with(111, bancho.BanchoGamemode.Osu)


@pytest.mark.asyncio
async def test_set_room():
    lobby, bl = make_lobby()
    await lobby.set_room(2, 3, 8)
    bl.set_settings.assert_called_once_with(
        bancho.BanchoLobbyTeamModes.TeamVs,
        bancho.BanchoLobbyWinConditions.ScoreV2,
        8,
    )


@pytest.mark.asyncio
async def test_set_room_no_size():
    lobby, bl = make_lobby()
    await lobby.set_room(0, 0)
    bl.set_settings.assert_called_once_with(
        bancho.BanchoLobbyTeamModes.HeadToHead,
        bancho.BanchoLobbyWinConditions.Score,
        None,
    )


@pytest.mark.asyncio
async def test_set_title():
    lobby, bl = make_lobby()
    await lobby.set_title("New Name")
    bl.set_name.assert_called_once_with("New Name")


@pytest.mark.asyncio
async def test_set_password_with_value():
    lobby, bl = make_lobby()
    await lobby.set_password("secret")
    bl.set_password.assert_called_once_with("secret")
    bl.clear_password.assert_not_called()


@pytest.mark.asyncio
async def test_set_password_empty_clears():
    lobby, bl = make_lobby()
    await lobby.set_password()
    bl.clear_password.assert_called_once()
    bl.set_password.assert_not_called()


# ------------------------------------------------------------------ player mgmt

@pytest.mark.asyncio
async def test_invite():
    lobby, bl = make_lobby()
    await lobby.invite("Alice")
    bl.invite_player.assert_called_once_with("Alice")


@pytest.mark.asyncio
async def test_kick():
    lobby, bl = make_lobby()
    await lobby.kick("Alice")
    bl.kick_player.assert_called_once_with("Alice")


@pytest.mark.asyncio
async def test_move():
    lobby, bl = make_lobby()
    await lobby.move("Alice", 3)
    bl.move_player.assert_called_once_with("Alice", 3)


@pytest.mark.asyncio
async def test_set_team_red():
    lobby, bl = make_lobby()
    await lobby.set_team("Alice", "red")
    bl.change_team.assert_called_once_with("Alice", bancho.BanchoLobbyTeams.Red)


@pytest.mark.asyncio
async def test_set_team_blue():
    lobby, bl = make_lobby()
    await lobby.set_team("Alice", "Blue")
    bl.change_team.assert_called_once_with("Alice", bancho.BanchoLobbyTeams.Blue)


@pytest.mark.asyncio
async def test_add_ref():
    lobby, bl = make_lobby()
    await lobby.add_ref("ref")
    bl.add_ref.assert_called_once_with("ref")


# ------------------------------------------------------------------ match flow

@pytest.mark.asyncio
async def test_start_no_delay():
    lobby, bl = make_lobby()
    await lobby.start()
    bl.start_match.assert_called_once_with(None)


@pytest.mark.asyncio
async def test_start_with_delay():
    lobby, bl = make_lobby()
    await lobby.start(delay=5)
    bl.start_match.assert_called_once_with(5)


@pytest.mark.asyncio
async def test_abort():
    lobby, bl = make_lobby()
    await lobby.abort()
    bl.abort_match.assert_called_once()


@pytest.mark.asyncio
async def test_timer():
    lobby, bl = make_lobby()
    await lobby.timer(60)
    bl.start_timer.assert_called_once_with(60)


@pytest.mark.asyncio
async def test_abort_timer():
    lobby, bl = make_lobby()
    await lobby.abort_timer()
    bl.abort_timer.assert_called_once()


@pytest.mark.asyncio
async def test_close():
    lobby, bl = make_lobby()
    await lobby.close()
    bl.close_lobby.assert_called_once()


@pytest.mark.asyncio
async def test_say():
    lobby, bl = make_lobby()
    await lobby.say("hello")
    bl.channel.send_message.assert_called_once_with("hello")


# ------------------------------------------------------------------ event callbacks

def test_on_match_started_clears_result():
    lobby, _ = make_lobby()
    lobby.last_result = MatchResult(scores=[PlayerResult("x", 100, True)])
    lobby._on_match_started()
    assert lobby.last_result.scores == []
    assert not lobby._match_finished_event.is_set()


def test_on_player_finished_appends_score():
    lobby, _ = make_lobby()
    lobby.last_result = MatchResult()
    score = MagicMock()
    score.player.user.username = "Alice"
    score.score = 500000
    score.passed = True
    lobby._on_player_finished(score)
    assert len(lobby.last_result.scores) == 1
    assert lobby.last_result.scores[0] == PlayerResult("Alice", 500000, True)


def test_on_player_finished_ignored_without_result():
    lobby, _ = make_lobby()
    lobby.last_result = None
    score = MagicMock(spec=bancho.BanchoLobbyPlayerScore)
    lobby._on_player_finished(score)  # should not raise


def test_on_match_finished_sets_event():
    lobby, _ = make_lobby()
    lobby._on_match_finished([])
    assert lobby._match_finished_event.is_set()


# ------------------------------------------------------------------ wait helpers

@pytest.mark.asyncio
async def test_wait_for_match_end():
    lobby, _ = make_lobby()
    lobby.last_result = MatchResult()
    lobby._match_finished_event.set()
    result = await lobby.wait_for_match_end()
    assert result is lobby.last_result


@pytest.mark.asyncio
async def test_wait_for_all_ready():
    lobby, _ = make_lobby()
    lobby._all_ready_event.set()
    await lobby.wait_for_all_ready()


@pytest.mark.asyncio
async def test_wait_for_timer():
    lobby, _ = make_lobby()
    lobby._timer_end_event.set()
    await lobby.wait_for_timer()
