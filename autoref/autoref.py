"""AutoRef: abstract base class for driving a Match through its steps."""
import asyncio
from abc import ABC, abstractmethod

import bancho

from .enums import Step, MapState
from .lobby import Lobby
from .models import Match, PlayableMap, Pool, Timers


def _normalize(name: str) -> str:
    return name.replace(" ", "_").casefold()


def _find_map(match: Match, beatmap_id: int) -> PlayableMap | None:
    stack = list(match.pool.maps)
    while stack:
        item = stack.pop()
        if isinstance(item, Pool):
            stack.extend(item.maps)
        elif item.beatmap_id == beatmap_id:
            return item
    return None


def _find_map_by_input(match: Match, text: str) -> PlayableMap | None:
    """Match a chat message against map name or code (space/underscore-insensitive).
    Only returns maps in PICKABLE or PROTECTED state."""
    from .enums import MapState
    needle = _normalize(text)
    stack = list(match.pool.maps)
    while stack:
        item = stack.pop()
        if isinstance(item, Pool):
            stack.extend(item.maps)
        elif item.name and _normalize(item.name) == needle:
            if item.state in (MapState.PICKABLE, MapState.PROTECTED):
                return item
    return None


class AutoRef(ABC):
    """Orchestrates a Match through pick/ban/protect steps.

    Subclass this and implement:
      - next_step(match_status) -> (team_index, Step)   [required]
      - handle_other(team_index)                         [required]
      - announce_*                                       [optional, have defaults]
    """

    def __init__(self, client: bancho.BanchoClient, match: Match, room_name: str,
                 timers: Timers | None = None):
        self._client = client
        self.match = match
        self.room_name = room_name
        self.timers = timers or Timers()
        self.lobby = Lobby(client)

    # ---------------------------------------------------------------- abstract

    @abstractmethod
    def next_step(self, match_status) -> tuple[int, Step]:
        """Return (team_index, Step) for the current match state."""

    @abstractmethod
    async def handle_other(self, team_index: int) -> None:
        """Handle a Step.OTHER turn — fully custom logic."""

    # ------------------------------------------------- awaiting player input

    async def _await_map_choice(self, team_index: int) -> int:
        """Wait for a player on team_index to name a map in chat. Returns beatmap_id."""
        team_usernames = {_normalize(p.username) for p in self.match.teams[team_index].players}
        loop = asyncio.get_event_loop()
        future: asyncio.Future[int] = loop.create_future()

        def on_message(msg: bancho.ChannelMessage) -> None:
            if future.done():
                return
            if _normalize(msg.user.username) not in team_usernames:
                return
            pm = _find_map_by_input(self.match, msg.message)
            if pm:
                future.set_result(pm.beatmap_id)

        self.lobby._lobby.channel.on("message", on_message)
        try:
            return await future
        finally:
            self.lobby._lobby.channel.remove_listener("message", on_message)

    async def await_pick(self, team_index: int) -> int:
        """Wait for the picking team to name a map. Override for custom input (e.g. Discord)."""
        return await self._await_map_choice(team_index)

    async def await_ban(self, team_index: int) -> int:
        """Wait for the banning team to name a map. Override for custom input."""
        return await self._await_map_choice(team_index)

    async def await_protect(self, team_index: int) -> int:
        """Wait for the protecting team to name a map. Override for custom input."""
        return await self._await_map_choice(team_index)

    # --------------------------------------------------------- default handlers

    async def handle_pick(self, team_index: int, beatmap_id: int) -> None:
        await self.announce_pick(team_index, beatmap_id)
        await self.play_map(beatmap_id, team_index, Step.PICK)

    async def handle_ban(self, team_index: int, beatmap_id: int) -> None:
        pm = _find_map(self.match, beatmap_id)
        if pm:
            pm.state = MapState.BANNED
        self.match.record_action(team_index, Step.BAN, beatmap_id)
        await self.announce_ban(team_index, beatmap_id)

    async def handle_protect(self, team_index: int, beatmap_id: int) -> None:
        pm = _find_map(self.match, beatmap_id)
        if pm:
            pm.state = MapState.PROTECTED
        self.match.record_action(team_index, Step.PROTECT, beatmap_id)
        await self.announce_protect(team_index, beatmap_id)

    # ---------------------------------------------------- overridable announces

    async def announce_pick(self, team_index: int, beatmap_id: int) -> None:
        team = self.match.teams[team_index]
        pm = _find_map(self.match, beatmap_id)
        name = pm.name if pm and pm.name else str(beatmap_id)
        await self.lobby.say(f"{team.name} picked {name}")

    async def announce_ban(self, team_index: int, beatmap_id: int) -> None:
        team = self.match.teams[team_index]
        pm = _find_map(self.match, beatmap_id)
        name = pm.name if pm and pm.name else str(beatmap_id)
        await self.lobby.say(f"{team.name} banned {name}")

    async def announce_protect(self, team_index: int, beatmap_id: int) -> None:
        team = self.match.teams[team_index]
        pm = _find_map(self.match, beatmap_id)
        name = pm.name if pm and pm.name else str(beatmap_id)
        await self.lobby.say(f"{team.name} protected {name}")

    async def announce_win(self, team_index: int) -> None:
        await self.lobby.say(f"{self.match.teams[team_index].name} wins!")

    async def announce_next_pick(self, team_index: int) -> None:
        await self.lobby.say(
            f"{self.match.teams[team_index].name}, you have {self.timers.pick}s to pick a map."
        )

    async def announce_next_ban(self, team_index: int) -> None:
        await self.lobby.say(
            f"{self.match.teams[team_index].name}, you have {self.timers.ban}s to ban a map."
        )

    async def announce_next_protect(self, team_index: int) -> None:
        await self.lobby.say(
            f"{self.match.teams[team_index].name}, you have {self.timers.protect}s to protect a map."
        )

    # ---------------------------------------------------------------- main loop

    async def run(self) -> None:
        ruleset = self.match.ruleset

        await self.lobby.create(self.room_name)
        await self.lobby.set_room(
            team_mode=ruleset.team_mode,
            score_mode=ruleset.win_condition.value - 1,
            size=ruleset.vs * 2 if ruleset.team_mode == 2 else ruleset.vs,
        )
        if ruleset.enforced_mods:
            await self.lobby.set_mods(str(ruleset.enforced_mods))

        for team in self.match.teams:
            for player in team.players:
                await self.lobby.invite(player.username)

        while True:
            team_index, step = self.next_step(self.match.match_status)

            if step == Step.WIN:
                await self.announce_win(team_index)
                break
            elif step == Step.PICK:
                await self.announce_next_pick(team_index)
                await self.lobby.timer(self.timers.pick)
                beatmap_id = await self.await_pick(team_index)
                await self.handle_pick(team_index, beatmap_id)
            elif step == Step.BAN:
                await self.announce_next_ban(team_index)
                await self.lobby.timer(self.timers.ban)
                beatmap_id = await self.await_ban(team_index)
                await self.handle_ban(team_index, beatmap_id)
            elif step == Step.PROTECT:
                await self.announce_next_protect(team_index)
                await self.lobby.timer(self.timers.protect)
                beatmap_id = await self.await_protect(team_index)
                await self.handle_protect(team_index, beatmap_id)
            elif step == Step.OTHER:
                await self.handle_other(team_index)

        await self.lobby.close()

    async def play_map(self, beatmap_id: int, team_index: int, step: Step) -> None:
        """Set the map, wait for ready, start, wait for result, record it."""
        pm = _find_map(self.match, beatmap_id)
        gamemode = self.match.ruleset.gamemode.value

        await self.lobby.set_map(beatmap_id, gamemode)
        if pm and pm.mods:
            await self.lobby.set_mods(str(pm.mods))

        await self.lobby.timer(self.timers.between_maps)
        await self.lobby.wait_for_all_ready()
        await self.lobby.start()
        result = await self.lobby.wait_for_match_end()

        self.match.record_action(team_index, step, beatmap_id)
        return result
