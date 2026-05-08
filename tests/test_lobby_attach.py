"""T46: Lobby.attach registers same event handlers as create. Idempotent if called twice."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, call
import pytest
import bancho

from autoref.core.lobby import Lobby


def _make_client(lobby_id=42):
    mock_lobby = MagicMock()
    mock_lobby.id = lobby_id
    mock_lobby.channel = MagicMock()
    mock_lobby.channel.on = MagicMock()
    mock_lobby.on = MagicMock()
    client = MagicMock(spec=bancho.BanchoClient)
    client.make_lobby = AsyncMock(return_value=mock_lobby)
    client.join_lobby = AsyncMock(return_value=mock_lobby)
    return client, mock_lobby


@pytest.mark.asyncio
async def test_attach_registers_handlers():
    client, mock_lobby = _make_client(42)
    lobby = Lobby(client)
    await lobby.attach(42)

    events = {c.args[0] for c in mock_lobby.on.call_args_list}
    assert "playerJoined" in events
    assert "playerLeft" in events
    assert "matchStarted" in events
    assert "matchFinished" in events
    mock_lobby.channel.on.assert_called_once_with("message", lobby._on_channel_message)


@pytest.mark.asyncio
async def test_create_registers_same_events():
    client, mock_lobby = _make_client(10)
    lobby = Lobby(client)
    await lobby.create("Room")

    events = {c.args[0] for c in mock_lobby.on.call_args_list}
    assert "playerJoined" in events
    assert "matchStarted" in events


@pytest.mark.asyncio
async def test_attach_idempotent():
    client, mock_lobby = _make_client(42)
    lobby = Lobby(client)
    await lobby.attach(42)
    first_call_count = client.join_lobby.call_count

    await lobby.attach(42)
    # join_lobby should not be called again
    assert client.join_lobby.call_count == first_call_count


@pytest.mark.asyncio
async def test_attach_uses_join_lobby():
    client, mock_lobby = _make_client(77)
    lobby = Lobby(client)
    result = await lobby.attach(77)
    client.join_lobby.assert_called_once_with(77)
    assert result == 77
    assert lobby._lobby is mock_lobby
