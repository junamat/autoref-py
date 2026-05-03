"""AutoRef: abstract base class for driving a Match through its steps."""
import asyncio
import logging
from abc import ABC, abstractmethod

import bancho

from ..enums import Step, MapState, RefMode
from ..lobby import Lobby
from ..models import Match, PlayableMap, Pool, Timers
from ..utils import find_map as _find_map, find_map_by_input as _find_map_by_input, find_map_by_input_pick as _find_map_by_input_pick, normalize_name as _normalize
from ..storage import MatchDatabase
from .scorer import MatchScorer
from .persister import MatchPersister
from .announcer import Announcer
from .broker import CommandBroker
from .player import PlayRunner
from .chooser import MapChooser
from ..commands import Command, COMMANDS, BUILTIN_HANDLERS  # re-exported for backwards compat

logger = logging.getLogger(__name__)






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
        mode: RefMode = RefMode.OFF,
        ref_prefix: str = ">",
        refs: set[str] | None = None,
        db: MatchDatabase | None = None,
        score_fetcher=None,
    ):
        self._client = client
        self.match = match
        self.scorer = MatchScorer(match)
        self.persister = MatchPersister(db)
        self.room_name = room_name
        self.timers = timers or Timers()
        self.lobby = Lobby(client)
        self.announcer = Announcer(self.lobby, match, self.timers)
        self.db = db
        self.score_fetcher = score_fetcher
        self._score_fetch_tasks: list[asyncio.Task] = []

        self.mode = mode
        self.ref_prefix = ref_prefix
        # Normalized ref usernames; empty set = anyone may use ref commands.
        self.refs: set[str] = {_normalize(r) for r in refs} if refs else set()

        self._mode_event = asyncio.Event()
        if mode != RefMode.OFF:
            self._mode_event.set()

        self._timeout_event = asyncio.Event()
        self._timeout_event.set()

        self._next_future: asyncio.Future | None = None
        self._step_cancel_future: asyncio.Future | None = None
        self._abort_event: asyncio.Event = asyncio.Event()
        self._map_in_progress: bool = False
        self._close_event: asyncio.Event = asyncio.Event()
        self._state_hooks: list = []
        self._pending_proposal: dict | None = None
        self.broker = CommandBroker(self)
        self.player = PlayRunner(self)
        self.chooser = MapChooser(self)
        self.lobby.add_input_hook(self._handle_input)
        self.lobby.add_presence_hook(self._push_state)

    # ------------------------------------------------------------ state hooks

    def add_state_hook(self, fn) -> None:
        """Register an async callback(state_dict) called after each state change."""
        self._state_hooks.append(fn)

    def _get_state(self) -> dict:
        """Build a serialisable state snapshot. Subclasses should call super() and extend."""
        from .._state_snapshot import build_state
        return build_state(self)

    async def _push_state(self) -> None:
        if not self._state_hooks:
            return
        state = self._get_state()
        for fn in self._state_hooks:
            try:
                await fn(state)
            except Exception:
                pass

    # ---------------------------------------------------------- informational helpers

    def _win_counts(self) -> list[int]:
        """Return map wins per team. Override in subclasses that track wins."""
        return [0] * len(self.match.teams)

    def _team_name(self, team_index: int) -> str:
        return self.scorer.team_name(team_index)

    def _format_step_history(self, step_name: str) -> str:
        return self.scorer.format_step_history(step_name)

    def _format_scoreline(self) -> str:
        return self.scorer.format_scoreline(self._win_counts())

    def _winner_index(self) -> int | None:
        """Return the winning team index if the match is decided, else None."""
        return self.scorer.winner_index(self._win_counts())

    def _save_match(self) -> None:
        """Persist match to the attached MatchDatabase, if any."""
        self.persister.save(self.match, self._winner_index())

    # ---------------------------------------------------------- step interruption

    def _cancel_step(self) -> None:
        """Wake up any active await_pick/ban/protect so the main loop can re-evaluate."""
        if self._next_future and not self._next_future.done():
            self._next_future.set_result(["__undo__"])
        if self._step_cancel_future and not self._step_cancel_future.done():
            self._step_cancel_future.set_result(None)

    async def _undo_last_action(self) -> bool:
        ms = self.match.match_status
        if ms.empty:
            await self.lobby.say("Nothing to undo.")
            return False
        last = ms.iloc[-1]
        step_name = str(last["step"])
        beatmap_id = int(last["beatmap_id"])
        team_idx = int(last["team_index"])
        self.match.match_status = ms.iloc[:-1].reset_index(drop=True)
        pm = _find_map(self.match, beatmap_id)
        if pm is not None:
            pm.state = MapState.PICKABLE
        code = pm.name if pm and pm.name else str(beatmap_id)
        await self.lobby.say(
            f"Undone: {self._team_name(team_idx)} {step_name.lower()} {code}. Step will repeat."
        )
        self._cancel_step()
        await self._push_state()
        return True

    # ---------------------------------------------------------- timeout

    async def _do_timeout(self, duration: int = 120) -> None:
        if not self._timeout_event.is_set():
            return  # already paused
        self._timeout_event.clear()
        mins = duration // 60
        secs = duration % 60
        label = f"{mins}m" if not secs else f"{mins}m{secs}s" if mins else f"{secs}s"
        await self.lobby.say(f"Timeout — {label} break. Resuming automatically.")
        await asyncio.sleep(duration)
        self._timeout_event.set()
        await self.lobby.say("Timeout over, resuming.")
        await self._push_state()

    # ---------------------------------------------------------------- abstract

    @abstractmethod
    def next_step(self, match_status) -> tuple[int, Step]:
        """Return (team_index, Step) for the current match state."""

    async def handle_other(self, team_index: int) -> None:
        """Handle a Step.OTHER turn — override for custom logic."""
        pass

    # ---------------------------------------------------------- mode management

    async def _set_mode(self, mode: RefMode) -> None:
        self.mode = mode
        if mode == RefMode.OFF:
            self._mode_event.clear()
        else:
            self._mode_event.set()
        logger.info("mode → %s", mode.value)
        await self._push_state()

    def _is_ref(self, username: str) -> bool:
        """True if username is allowed to use ref commands (or refs list is empty)."""
        return not self.refs or _normalize(username) in self.refs

    def _trusted_sources(self) -> set[str]:
        """Sources that are not Bancho chat — reply sinks are registered for these."""
        return set(self.lobby._reply_sinks.keys())

    def _commands(self) -> list[Command]:
        """All commands for this instance. Subclasses can override to extend."""
        return list(COMMANDS)

    def _help_ref_lines(self) -> list[str]:
        lines = []
        current_section = None
        for cmd in self._commands():
            if cmd.section != current_section:
                current_section = cmd.section
                lines.append(f"── {cmd.section} ──")
            prefix = "" if cmd.noprefix else ">"
            aliases = "".join(f" / {prefix}{a}" for a in cmd.aliases)
            usage = f" {cmd.usage}" if cmd.usage else ""
            desc = f"  — {cmd.desc}" if cmd.desc else ""
            lines.append(f"{prefix}{cmd.name}{aliases}{usage}{desc}")
        return lines

    async def _dispatch_command(self, cmd: str, args: list[str], source: str) -> bool:
        """Execute a parsed ref command. Returns True if recognised."""
        handler = BUILTIN_HANDLERS.get(cmd)
        if handler is None:
            return False
        await handler(self, args, source)
        return True

    async def _handle_input(self, text: str, source: str) -> bool:
        return await self.broker.handle_input(text, source)

    async def _run_command_broker(self) -> None:
        await self.broker.run_loop()

    # ------------------------------------------------- awaiting player input

    async def _await_map_choice(self, team_index: int, for_ban: bool = False) -> int | None:
        return await self.chooser.await_map_choice(team_index, for_ban)

    async def _await_map_from_ref(self, for_ban: bool = False) -> int | None:
        return await self.chooser.await_map_from_ref(for_ban)

    async def _await_map_assisted(self, team_index: int, step: Step) -> int | None:
        return await self.chooser.await_map_assisted(team_index, step)

    async def await_pick(self, team_index: int) -> int | None:
        return await self.chooser.await_pick(team_index)

    async def await_ban(self, team_index: int) -> int | None:
        return await self.chooser.await_ban(team_index)

    async def await_protect(self, team_index: int) -> int | None:
        return await self.chooser.await_protect(team_index)

    async def handle_pick(self, team_index: int, beatmap_id: int) -> None:
        await self.chooser.handle_pick(team_index, beatmap_id)

    async def handle_ban(self, team_index: int, beatmap_id: int) -> None:
        await self.chooser.handle_ban(team_index, beatmap_id)

    async def handle_protect(self, team_index: int, beatmap_id: int) -> None:
        await self.chooser.handle_protect(team_index, beatmap_id)

    async def _pre_pick(self, team_index: int) -> None:
        """Called just before await_pick. Override to suppress or replace the pick timer."""
        await self.chooser.pre_pick(team_index)

    async def announce_pick(self, team_index: int, beatmap_id: int) -> None:
        await self.announcer.pick(team_index, beatmap_id)

    async def announce_ban(self, team_index: int, beatmap_id: int) -> None:
        await self.announcer.ban(team_index, beatmap_id)

    async def announce_protect(self, team_index: int, beatmap_id: int) -> None:
        await self.announcer.protect(team_index, beatmap_id)

    async def announce_finish(self, team_index: int) -> None:
        await self.announcer.finish(team_index)

    async def announce_closing(self) -> None:
        await self.announcer.closing()

    async def announce_next_pick(self, team_index: int) -> None:
        await self.announcer.next_pick(team_index)

    async def announce_next_ban(self, team_index: int) -> None:
        await self.announcer.next_ban(team_index)

    async def announce_next_protect(self, team_index: int) -> None:
        await self.announcer.next_protect(team_index)

    # ---------------------------------------------------------------- main loop

    async def _pre_loop(self) -> None:
        """Hook for subclasses to run setup (roll, scheme choice, ...) after the
        lobby is up but before entering the pick/ban/protect dispatch loop."""
        return None

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

        # Auto-assign teams when players join
        async def auto_assign_teams():
            for team_idx, team in enumerate(self.match.teams):
                team_color = "Blue" if team_idx == 0 else "Red"
                for player in team.players:
                    if _normalize(player.username) in {_normalize(p) for p in self.lobby.players}:
                        try:
                            await self.lobby.set_team(player.username, team_color)
                        except Exception:
                            pass  # Player might not be in lobby yet
        
        self.lobby.add_presence_hook(auto_assign_teams)

        broker_task = asyncio.create_task(self._run_command_broker())
        cli_task = asyncio.create_task(self.lobby.run_cli_input())
        try:
            await self._pre_loop()
            await self._push_state()
            while True:
                # Pause during an active timeout (any user can trigger >timeout).
                await self._timeout_event.wait()
                # Pause here while OFF; resumes when ref switches to assisted/auto.
                if self.mode == RefMode.OFF:
                    await self._mode_event.wait()

                if self._close_event.is_set():
                    break

                team_index, step = self.next_step(self.match.match_status)

                if step == Step.FINISH:
                    await self.announce_finish(team_index)
                    break
                elif step == Step.PICK:
                    await self._pre_pick(team_index)
                    beatmap_id = await self.await_pick(team_index)
                    if beatmap_id is None:
                        await self._push_state()
                        continue
                    await self.handle_pick(team_index, beatmap_id)
                    await self._push_state()
                elif step == Step.BAN:
                    if self.mode != RefMode.OFF:
                        await self.announce_next_ban(team_index)
                        await self.lobby.timer(self.timers.ban)
                    beatmap_id = await self.await_ban(team_index)
                    if beatmap_id is None:
                        await self._push_state()
                        continue
                    await self.handle_ban(team_index, beatmap_id)
                    await self._push_state()
                elif step == Step.PROTECT:
                    if self.mode != RefMode.OFF:
                        await self.announce_next_protect(team_index)
                        await self.lobby.timer(self.timers.protect)
                    beatmap_id = await self.await_protect(team_index)
                    if beatmap_id is None:
                        await self._push_state()
                        continue
                    await self.handle_protect(team_index, beatmap_id)
                    await self._push_state()
                elif step == Step.OTHER:
                    await self.handle_other(team_index)
                    await self._push_state()
            await self.announce_closing()
            await asyncio.sleep(self.timers.closing)
        finally:
            broker_task.cancel()
            cli_task.cancel()
            await asyncio.gather(broker_task, cli_task, return_exceptions=True)
            # Drain pending API enrichment tasks so save_match() catches their results.
            if self._score_fetch_tasks:
                await asyncio.gather(*self._score_fetch_tasks, return_exceptions=True)
            if self.score_fetcher is not None:
                await self.score_fetcher.aclose()
            await self.lobby.close()

    async def play_map(self, beatmap_id: int, team_index: int, step: Step):
        return await self.player.play_map(beatmap_id, team_index, step)

    def _spawn_score_fetch(self, turn: int, beatmap_id: int) -> None:
        self.player.spawn_score_fetch(turn, beatmap_id)

    async def _do_score_fetch(self, turn: int, beatmap_id: int, lobby_id: int) -> None:
        await self.player.do_score_fetch(turn, beatmap_id, lobby_id)
