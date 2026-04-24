"""AutoRef: abstract base class for driving a Match through its steps."""
import asyncio
import logging
from abc import ABC, abstractmethod

import bancho

from .enums import Step, MapState, RefMode
from .lobby import Lobby
from .models import Match, PlayableMap, Pool, Timers

logger = logging.getLogger(__name__)


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

    Modes
    -----
    AUTO     — fully automatic (default)
    ASSISTED — bot announces and tracks; ref confirms each step with >next <map>
    OFF      — bot is silent; ref drives everything with ref commands

    Any player can type !panic at any time to switch to OFF.
    Refs switch modes with >mode <off|assisted|auto>.
    """

    def __init__(
        self,
        client: bancho.BanchoClient,
        match: Match,
        room_name: str,
        timers: Timers | None = None,
        mode: RefMode = RefMode.AUTO,
        ref_prefix: str = ">",
        refs: set[str] | None = None,
    ):
        self._client = client
        self.match = match
        self.room_name = room_name
        self.timers = timers or Timers()
        self.lobby = Lobby(client)

        self.mode = mode
        self.ref_prefix = ref_prefix
        # Normalized ref usernames; empty set = anyone may use ref commands.
        self.refs: set[str] = {_normalize(r) for r in refs} if refs else set()

        self._mode_event = asyncio.Event()
        if mode != RefMode.OFF:
            self._mode_event.set()

        self._next_future: asyncio.Future | None = None
        self.lobby.add_input_hook(self._handle_input)

    # ---------------------------------------------------------------- abstract

    @abstractmethod
    def next_step(self, match_status) -> tuple[int, Step]:
        """Return (team_index, Step) for the current match state."""

    @abstractmethod
    async def handle_other(self, team_index: int) -> None:
        """Handle a Step.OTHER turn — fully custom logic."""

    # ---------------------------------------------------------- mode management

    async def _set_mode(self, mode: RefMode) -> None:
        self.mode = mode
        if mode == RefMode.OFF:
            self._mode_event.clear()
        else:
            self._mode_event.set()
        logger.info("mode → %s", mode.value)

    def _is_ref(self, username: str) -> bool:
        """True if username is allowed to use ref commands (or refs list is empty)."""
        return not self.refs or _normalize(username) in self.refs

    async def _dispatch_command(self, cmd: str, args: list[str], source: str) -> bool:
        """Execute a parsed ref command. Returns True if recognised."""
        if cmd == "mode" and args:
            try:
                await self._set_mode(RefMode(args[0].lower()))
                await self.lobby.say(f"Mode: {self.mode.value}.")
            except ValueError:
                pass
            return True
        if cmd == "next":
            if self._next_future is not None and not self._next_future.done():
                self._next_future.set_result(args)
            return True
        return False

    async def _handle_input(self, text: str, source: str) -> bool:
        """Input hook for CLI/web lines. CLI/web is always trusted (no refs check)."""
        stripped = text.strip()
        if stripped == "!panic":
            await self._set_mode(RefMode.OFF)
            await self.lobby.say(f"!panic from {source} — switching to off mode.")
            return True
        if stripped.startswith(self.ref_prefix):
            parts = stripped[len(self.ref_prefix):].split()
            if parts:
                return await self._dispatch_command(parts[0].lower(), parts[1:], source)
        return False

    async def _run_command_broker(self) -> None:
        """Background task: routes !panic and ref-prefix commands from the lobby channel."""
        queue: asyncio.Queue = asyncio.Queue()

        def on_msg(msg) -> None:
            asyncio.ensure_future(queue.put(msg))

        self.lobby.channel.on("message", on_msg)
        try:
            while True:
                msg = await queue.get()
                text = msg.message.strip()
                if text == "!panic":
                    await self._set_mode(RefMode.OFF)
                    await self.lobby.say(f"!panic by {msg.user.username} — switching to off mode.")
                elif text.startswith(self.ref_prefix) and self._is_ref(msg.user.username):
                    parts = text[len(self.ref_prefix):].split()
                    if parts:
                        await self._dispatch_command(parts[0].lower(), parts[1:], msg.user.username)
        except asyncio.CancelledError:
            pass
        finally:
            self.lobby.channel.remove_listener("message", on_msg)

    # ------------------------------------------------- awaiting player input

    async def _await_map_choice(self, team_index: int) -> int:
        """Wait for a player on team_index to name a map in chat. Returns beatmap_id."""
        team_usernames = {_normalize(p.username) for p in self.match.teams[team_index].players}
        future: asyncio.Future[int] = asyncio.get_event_loop().create_future()

        def on_message(msg: bancho.ChannelMessage) -> None:
            if future.done():
                return
            if _normalize(msg.user.username) not in team_usernames:
                return
            pm = _find_map_by_input(self.match, msg.message)
            if pm:
                future.set_result(pm.beatmap_id)

        self.lobby.channel.on("message", on_message)
        try:
            return await future
        finally:
            self.lobby.channel.remove_listener("message", on_message)

    async def _await_map_from_ref(self) -> int:
        """Wait for >next <map_code> from any source (channel, CLI, web). Retries on unknown map."""
        while True:
            self._next_future = asyncio.get_event_loop().create_future()
            try:
                args = await self._next_future
            finally:
                self._next_future = None
            if args:
                pm = _find_map_by_input(self.match, " ".join(args))
                if pm:
                    return pm.beatmap_id
            await self.lobby.say(f"Unknown map. Usage: {self.ref_prefix}next <map_code>")

    async def await_pick(self, team_index: int) -> int:
        if self.mode in (RefMode.ASSISTED, RefMode.OFF):
            return await self._await_map_from_ref()
        return await self._await_map_choice(team_index)

    async def await_ban(self, team_index: int) -> int:
        if self.mode in (RefMode.ASSISTED, RefMode.OFF):
            return await self._await_map_from_ref()
        return await self._await_map_choice(team_index)

    async def await_protect(self, team_index: int) -> int:
        if self.mode in (RefMode.ASSISTED, RefMode.OFF):
            return await self._await_map_from_ref()
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

    async def announce_closing(self) -> None:
        await self.lobby.say(f"Lobby closing in {self.timers.closing}s.")

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
        wc = ruleset.win_condition.value
        await self.lobby.set_room(
            team_mode=ruleset.team_mode,
            score_mode=wc if 0 <= wc <= 3 else 3,
            size=ruleset.vs * 2 if ruleset.team_mode == 2 else ruleset.vs,
        )
        if ruleset.enforced_mods:
            await self.lobby.set_mods(str(ruleset.enforced_mods))

        for team in self.match.teams:
            for player in team.players:
                await self.lobby.invite(player.username)

        broker_task = asyncio.create_task(self._run_command_broker())
        cli_task = asyncio.create_task(self.lobby.run_cli_input())
        try:
            while True:
                # Pause here while OFF; resumes when ref switches to assisted/auto.
                if self.mode == RefMode.OFF:
                    await self._mode_event.wait()

                team_index, step = self.next_step(self.match.match_status)

                if step == Step.WIN:
                    await self.announce_win(team_index)
                    break
                elif step == Step.PICK:
                    if self.mode != RefMode.OFF:
                        await self.announce_next_pick(team_index)
                        await self.lobby.timer(self.timers.pick)
                    beatmap_id = await self.await_pick(team_index)
                    await self.handle_pick(team_index, beatmap_id)
                elif step == Step.BAN:
                    if self.mode != RefMode.OFF:
                        await self.announce_next_ban(team_index)
                        await self.lobby.timer(self.timers.ban)
                    beatmap_id = await self.await_ban(team_index)
                    await self.handle_ban(team_index, beatmap_id)
                elif step == Step.PROTECT:
                    if self.mode != RefMode.OFF:
                        await self.announce_next_protect(team_index)
                        await self.lobby.timer(self.timers.protect)
                    beatmap_id = await self.await_protect(team_index)
                    await self.handle_protect(team_index, beatmap_id)
                elif step == Step.OTHER:
                    await self.handle_other(team_index)
            await self.announce_closing()
            await asyncio.sleep(self.timers.closing)
        finally:
            broker_task.cancel()
            cli_task.cancel()
            await asyncio.gather(broker_task, cli_task, return_exceptions=True)
            await self.lobby.close()

    async def play_map(self, beatmap_id: int, team_index: int, step: Step) -> None:
        """Set the map, wait for ready, start, wait for result, record it."""
        pm = _find_map(self.match, beatmap_id)
        gamemode = self.match.ruleset.gamemode.value
        mods = pm.effective_mods() if pm else None

        await self.lobby.set_map(beatmap_id, gamemode)
        enforced = self.match.ruleset.enforced_mods
        extra = str(mods) if mods else ""
        base = str(enforced) if enforced else ""
        combined = extra if "Freemod" in extra else (extra + base)
        if combined:
            await self.lobby.set_mods(combined)

        await self.lobby.timer(self.timers.between_maps)
        ready_t = asyncio.create_task(self.lobby.wait_for_all_ready())
        timer_t = asyncio.create_task(self.lobby.wait_for_timer())
        await asyncio.wait([ready_t, timer_t], return_when=asyncio.FIRST_COMPLETED)
        ready_t.cancel()
        timer_t.cancel()
        await asyncio.gather(ready_t, timer_t, return_exceptions=True)
        await self.lobby.start(delay=self.timers.force_start)
        result = await self.lobby.wait_for_match_end()

        self.match.record_action(team_index, step, beatmap_id)
        return result
