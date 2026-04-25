"""Output sink protocol for bot messages.

Any async callable matching ``OutputSink`` can be registered on a Lobby via
``lobby.add_output_sink(fn)``.  It will be called for every message the bot
sends to the room, regardless of transport (Bancho, Discord, CLI echo, …).

Usage::

    async def discord_sink(text: str) -> None:
        await discord_channel.send(text)

    lobby.add_output_sink(discord_sink)
"""
from typing import Protocol, runtime_checkable


@runtime_checkable
class OutputSink(Protocol):
    async def __call__(self, text: str) -> None: ...
