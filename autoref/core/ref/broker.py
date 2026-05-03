"""CommandBroker: routes !panic and ref-prefix commands from chat / CLI / web inputs.

Holds a reference to the owning AutoRef to invoke dispatch + panic flow.
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from ..enums import RefMode

if TYPE_CHECKING:
    from .base import AutoRef


class CommandBroker:
    def __init__(self, ref: "AutoRef"):
        self.ref = ref

    async def handle_input(self, text: str, source: str) -> bool:
        """Input hook for CLI/web lines. CLI/web is always trusted (no refs check)."""
        ref = self.ref
        stripped = text.strip()
        if stripped == "!panic":
            await ref._set_mode(RefMode.OFF)
            await ref.lobby.say(f"!panic from {source} — switching to off mode.")
            return True
        if stripped.startswith(ref.ref_prefix):
            parts = stripped[len(ref.ref_prefix):].split()
            if parts:
                return await ref._dispatch_command(parts[0].lower(), parts[1:], source)
        return False

    async def run_loop(self) -> None:
        """Background task: routes !panic and ref-prefix commands from the lobby channel."""
        ref = self.ref
        queue: asyncio.Queue = asyncio.Queue()

        def on_msg(msg) -> None:
            asyncio.ensure_future(queue.put(msg))

        ref.lobby.channel.on("message", on_msg)
        try:
            while True:
                msg = await queue.get()
                text = msg.message.strip()
                if text == "!panic":
                    await ref._set_mode(RefMode.OFF)
                    await ref.lobby.say(f"!panic by {msg.user.username} — switching to off mode.")
                elif text.startswith(ref.ref_prefix):
                    parts = text[len(ref.ref_prefix):].split()
                    if parts:
                        cmd = parts[0].lower()
                        # timeout is usable by anyone, not just registered refs
                        if cmd in ("timeout", "to", "pause"):
                            await ref._dispatch_command(cmd, parts[1:], msg.user.username)
                        elif ref._is_ref(msg.user.username):
                            await ref._dispatch_command(cmd, parts[1:], msg.user.username)
        except asyncio.CancelledError:
            pass
        finally:
            ref.lobby.channel.remove_listener("message", on_msg)
