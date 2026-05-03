"""MapChooser: awaits player/ref map choices and applies pick/ban/protect outcomes."""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import bancho

from ..enums import MapState, RefMode, Step
from ..utils import (
    find_map as _find_map,
    find_map_by_input as _find_map_by_input,
    find_map_by_input_pick as _find_map_by_input_pick,
    normalize_name as _normalize,
)

if TYPE_CHECKING:
    from .base import AutoRef


class MapChooser:
    def __init__(self, ref: "AutoRef"):
        self.ref = ref

    async def await_map_choice(self, team_index: int, for_ban: bool = False) -> int | None:
        """Wait for a player on team_index to name a map in chat. Returns beatmap_id or None on undo."""
        ref = self.ref
        team_usernames = {_normalize(p.username) for p in ref.match.teams[team_index].players}
        loop = asyncio.get_event_loop()
        map_future: asyncio.Future[int] = loop.create_future()
        ref._step_cancel_future = loop.create_future()

        def on_message(msg: bancho.ChannelMessage) -> None:
            if map_future.done():
                return
            if _normalize(msg.user.username) not in team_usernames:
                return
            finder = _find_map_by_input if for_ban else _find_map_by_input_pick
            pm = finder(ref.match, msg.message)
            if pm:
                map_future.set_result(pm.beatmap_id)
            elif _find_map_by_input_pick(ref.match, msg.message):
                asyncio.ensure_future(ref.lobby.say(
                    f"{msg.message} is protected and cannot be banned."
                ))

        ref.lobby.channel.on("message", on_message)
        try:
            done, pending = await asyncio.wait(
                {map_future, ref._step_cancel_future},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for f in pending:
                f.cancel()
            if ref._step_cancel_future in done:
                return None
            return map_future.result()
        finally:
            ref._step_cancel_future = None
            ref.lobby.channel.remove_listener("message", on_message)

    async def await_map_from_ref(self, for_ban: bool = False) -> int | None:
        """Wait for >next <map_code> from any source. Returns beatmap_id or None on undo."""
        ref = self.ref
        while True:
            ref._next_future = asyncio.get_event_loop().create_future()
            try:
                args = await ref._next_future
            finally:
                ref._next_future = None
            if args == ["__undo__"]:
                return None
            if args:
                text = " ".join(args)
                finder = _find_map_by_input if for_ban else _find_map_by_input_pick
                pm = finder(ref.match, text)
                if pm:
                    return pm.beatmap_id
                if for_ban and _find_map_by_input_pick(ref.match, text):
                    await ref.lobby.say(f"{text} is protected and cannot be banned.")
                else:
                    await ref.lobby.say(f"Unknown or unavailable map: {text}. Usage: {ref.ref_prefix}next <map_code>")

    async def await_map_assisted(self, team_index: int, step: Step) -> int | None:
        """ASSISTED mode: watch for a player's map choice, surface as proposal, wait for ref confirm."""
        ref = self.ref
        team_usernames = {_normalize(p.username) for p in ref.match.teams[team_index].players}
        for_ban = (step == Step.BAN)

        def on_message(msg) -> None:
            if _normalize(getattr(msg.user, "username", "")) not in team_usernames:
                return
            finder = _find_map_by_input if for_ban else _find_map_by_input_pick
            pm = finder(ref.match, msg.message)
            if pm is not None:
                ref._pending_proposal = {
                    "step": step.name,
                    "team_index": team_index,
                    "map": pm.name or str(pm.beatmap_id),
                    "beatmap_id": pm.beatmap_id,
                }
                asyncio.ensure_future(ref._push_state())
            elif for_ban and _find_map_by_input_pick(ref.match, msg.message):
                asyncio.ensure_future(ref.lobby.say(
                    f"{msg.message} is protected and cannot be banned."
                ))

        ref.lobby.channel.on("message", on_message)
        try:
            return await self.await_map_from_ref()
        finally:
            ref.lobby.channel.remove_listener("message", on_message)
            ref._pending_proposal = None

    async def await_pick(self, team_index: int) -> int | None:
        ref = self.ref
        if ref.mode == RefMode.ASSISTED:
            return await self.await_map_assisted(team_index, Step.PICK)
        if ref.mode == RefMode.OFF:
            return await self.await_map_from_ref(for_ban=False)
        return await self.await_map_choice(team_index, for_ban=False)

    async def await_ban(self, team_index: int) -> int | None:
        ref = self.ref
        if ref.mode == RefMode.ASSISTED:
            return await self.await_map_assisted(team_index, Step.BAN)
        if ref.mode == RefMode.OFF:
            return await self.await_map_from_ref(for_ban=True)
        return await self.await_map_choice(team_index, for_ban=True)

    async def await_protect(self, team_index: int) -> int | None:
        ref = self.ref
        if ref.mode == RefMode.ASSISTED:
            return await self.await_map_assisted(team_index, Step.PROTECT)
        if ref.mode == RefMode.OFF:
            return await self.await_map_from_ref(for_ban=False)
        return await self.await_map_choice(team_index, for_ban=False)

    async def handle_pick(self, team_index: int, beatmap_id: int) -> None:
        ref = self.ref
        await ref.announce_pick(team_index, beatmap_id)
        pm = _find_map(ref.match, beatmap_id)
        if pm is not None:
            pm.state = MapState.PLAYED
        await ref.play_map(beatmap_id, team_index, Step.PICK)

    async def handle_ban(self, team_index: int, beatmap_id: int) -> None:
        ref = self.ref
        pm = _find_map(ref.match, beatmap_id)
        if pm:
            pm.state = MapState.BANNED
        ref.match.record_action(team_index, Step.BAN, beatmap_id)
        await ref.announce_ban(team_index, beatmap_id)

    async def handle_protect(self, team_index: int, beatmap_id: int) -> None:
        ref = self.ref
        pm = _find_map(ref.match, beatmap_id)
        if pm:
            pm.state = MapState.PROTECTED
        ref.match.record_action(team_index, Step.PROTECT, beatmap_id)
        await ref.announce_protect(team_index, beatmap_id)

    async def pre_pick(self, team_index: int) -> None:
        """Called just before await_pick. Override on AutoRef to suppress or replace the pick timer."""
        ref = self.ref
        if ref.mode != RefMode.OFF:
            await ref.announce_next_pick(team_index)
            await ref.lobby.timer(ref.timers.pick)
