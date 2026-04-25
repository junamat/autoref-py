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

        self._timeout_event = asyncio.Event()
        self._timeout_event.set()

        self._next_future: asyncio.Future | None = None
        self._step_cancel_future: asyncio.Future | None = None
        self._abort_event: asyncio.Event = asyncio.Event()
        self._map_in_progress: bool = False
        self._state_hooks: list = []
        self._pending_proposal: dict | None = None
        self.lobby.add_input_hook(self._handle_input)

    # ------------------------------------------------------------ state hooks

    def add_state_hook(self, fn) -> None:
        """Register an async callback(state_dict) called after each state change."""
        self._state_hooks.append(fn)

    def _get_state(self) -> dict:
        """Build a serialisable state snapshot. Subclasses should call super() and extend."""
        played_ids: set[int] = set()
        if not self.match.match_status.empty:
            for bid in self.match.match_status.loc[
                self.match.match_status["step"] == "PICK", "beatmap_id"
            ]:
                played_ids.add(int(bid))

        maps = []
        for pm in self.match.pool.flatten():
            if int(pm.beatmap_id) in played_ids:
                map_state = "played"
            elif pm.state == MapState.BANNED:
                map_state = "banned"
            elif pm.state == MapState.PROTECTED:
                map_state = "protected"
            elif pm.state == MapState.DISALLOWED:
                map_state = "disallowed"
            else:
                map_state = "pickable"
            maps.append({
                "code": pm.name or str(pm.beatmap_id),
                "state": map_state,
                "tb": getattr(pm, "is_tiebreaker", False),
            })

        events = []
        for _, row in self.match.match_status.iterrows():
            ti = int(row["team_index"])
            team_name = (
                self.match.teams[ti].name if ti < len(self.match.teams) else str(ti)
            )
            pm = _find_map(self.match, int(row["beatmap_id"]))
            map_code = pm.name if pm and pm.name else str(row["beatmap_id"])
            events.append({"step": str(row["step"]), "team": team_name, "map": map_code})

        teams = [
            {"name": t.name, "players": [{"username": p.username} for p in t.players]}
            for t in self.match.teams
        ]

        return {
            "mode": self.mode.value,
            "team_names": [t.name for t in self.match.teams],
            "teams": teams,
            "best_of": self.match.ruleset.best_of,
            "maps": maps,
            "events": events,
            "pending_proposal": self._pending_proposal,
            "ref_name": getattr(self._client, "username", None),
        }

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
        if team_index < len(self.match.teams):
            return self.match.teams[team_index].name
        return str(team_index)

    def _format_step_history(self, step_name: str) -> str:
        ms = self.match.match_status
        if ms.empty:
            return "none"
        rows = ms[ms["step"] == step_name]
        if rows.empty:
            return "none"
        parts = []
        for _, row in rows.iterrows():
            pm = _find_map(self.match, int(row["beatmap_id"]))
            code = pm.name if pm and pm.name else str(row["beatmap_id"])
            parts.append(f"{self._team_name(int(row['team_index']))} {code}")
        return ", ".join(parts)

    def _format_scoreline(self) -> str:
        wins = self._win_counts()
        bo = self.match.ruleset.best_of
        needed = bo // 2 + 1
        if len(wins) == 2:
            return (f"{self._team_name(0)} {wins[0]} : {wins[1]} {self._team_name(1)}"
                    f" (BO{bo}, first to {needed})")
        return " | ".join(f"{self._team_name(i)}: {wins[i]}" for i in range(len(wins)))

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
        await self._push_state()

    def _is_ref(self, username: str) -> bool:
        """True if username is allowed to use ref commands (or refs list is empty)."""
        return not self.refs or _normalize(username) in self.refs

    async def _dispatch_command(self, cmd: str, args: list[str], source: str) -> bool:
        """Execute a parsed ref command. Returns True if recognised."""

        # ── mode / flow ──────────────────────────────────────────────────────
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

        if cmd == "dismiss":
            self._pending_proposal = None
            await self._push_state()
            return True

        # ── timeout (also routed here from CLI/web; channel path bypasses ref check) ──
        if cmd in ("timeout", "to", "pause"):
            duration = 120
            if args:
                try:
                    duration = int(args[0])
                except ValueError:
                    pass
            asyncio.ensure_future(self._do_timeout(duration))
            return True

        # ── informational ────────────────────────────────────────────────────
        if cmd in ("scoreline", "score", "sc"):
            await self.lobby.say(self._format_scoreline())
            return True

        if cmd in ("picks", "pk"):
            await self.lobby.say(f"picks: {self._format_step_history('PICK')}")
            return True

        if cmd in ("bans", "bn"):
            await self.lobby.say(f"bans: {self._format_step_history('BAN')}")
            return True

        if cmd in ("protects", "pro", "prot"):
            await self.lobby.say(f"protects: {self._format_step_history('PROTECT')}")
            return True

        if cmd in ("status", "st"):
            bo = self.match.ruleset.best_of
            await self.lobby.say(
                f"[status] BO{bo} | {self.mode.value} mode | {self._format_scoreline()}"
            )
            bans = self._format_step_history("BAN")
            pros = self._format_step_history("PROTECT")
            pks  = self._format_step_history("PICK")
            if pros != "none":
                await self.lobby.say(f"protects: {pros} | bans: {bans}")
            else:
                await self.lobby.say(f"bans: {bans}")
            await self.lobby.say(f"picks: {pks}")
            return True

        # ── lobby control ────────────────────────────────────────────────────
        if cmd in ("setmap", "sm", "map") and args:
            try:
                bid = int(args[0])
                gm  = int(args[1]) if len(args) > 1 else self.match.ruleset.gamemode.value
                await self.lobby.set_map(bid, gm)
            except (ValueError, IndexError):
                await self.lobby.say(f"Usage: {self.ref_prefix}setmap <beatmap_id> [gamemode]")
            return True

        if cmd in ("timer", "t", "ti") and args:
            _named = {
                "pick": self.timers.pick,
                "ban": self.timers.ban,
                "protect": self.timers.protect, "pro": self.timers.protect,
                "between": self.timers.between_maps, "btw": self.timers.between_maps,
                "ready": self.timers.ready_up,
                "force": self.timers.force_start, "fs": self.timers.force_start,
                "closing": self.timers.closing,
            }
            raw = args[0].lower()
            seconds = _named.get(raw)
            if seconds is None:
                try:
                    seconds = int(args[0])
                except ValueError:
                    await self.lobby.say(
                        f"Usage: {self.ref_prefix}timer <seconds|pick|ban|protect|between|ready|force|closing>"
                    )
                    return True
            asyncio.ensure_future(self.lobby.timer(seconds))
            return True

        if cmd in ("startmap", "start", "go"):
            delay = self.timers.force_start
            if args:
                try:
                    delay = int(args[0])
                except ValueError:
                    pass
            asyncio.ensure_future(self.lobby.start(delay=delay))
            return True

        if cmd in ("abort", "ab"):
            if self._map_in_progress:
                await self.lobby.abort()
                self._abort_event.set()
            else:
                await self.lobby.say("No map in progress.")
            return True

        if cmd in ("undo", "u"):
            await self._undo_last_action()
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
                elif text.startswith(self.ref_prefix):
                    parts = text[len(self.ref_prefix):].split()
                    if parts:
                        cmd = parts[0].lower()
                        # timeout is usable by anyone, not just registered refs
                        if cmd in ("timeout", "to", "pause"):
                            await self._dispatch_command(cmd, parts[1:], msg.user.username)
                        elif self._is_ref(msg.user.username):
                            await self._dispatch_command(cmd, parts[1:], msg.user.username)
        except asyncio.CancelledError:
            pass
        finally:
            self.lobby.channel.remove_listener("message", on_msg)

    # ------------------------------------------------- awaiting player input

    async def _await_map_choice(self, team_index: int) -> int | None:
        """Wait for a player on team_index to name a map in chat. Returns beatmap_id or None on undo."""
        team_usernames = {_normalize(p.username) for p in self.match.teams[team_index].players}
        loop = asyncio.get_event_loop()
        map_future: asyncio.Future[int] = loop.create_future()
        self._step_cancel_future = loop.create_future()

        def on_message(msg: bancho.ChannelMessage) -> None:
            if map_future.done():
                return
            if _normalize(msg.user.username) not in team_usernames:
                return
            pm = _find_map_by_input(self.match, msg.message)
            if pm:
                map_future.set_result(pm.beatmap_id)

        self.lobby.channel.on("message", on_message)
        try:
            done, pending = await asyncio.wait(
                {map_future, self._step_cancel_future},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for f in pending:
                f.cancel()
            if self._step_cancel_future in done:
                return None
            return map_future.result()
        finally:
            self._step_cancel_future = None
            self.lobby.channel.remove_listener("message", on_message)

    async def _await_map_from_ref(self) -> int | None:
        """Wait for >next <map_code> from any source. Returns beatmap_id or None on undo."""
        while True:
            self._next_future = asyncio.get_event_loop().create_future()
            try:
                args = await self._next_future
            finally:
                self._next_future = None
            if args == ["__undo__"]:
                return None
            if args:
                pm = _find_map_by_input(self.match, " ".join(args))
                if pm:
                    return pm.beatmap_id
            await self.lobby.say(f"Unknown map. Usage: {self.ref_prefix}next <map_code>")

    async def _await_map_assisted(self, team_index: int, step: Step) -> int | None:
        """ASSISTED mode: watch for a player's map choice, surface as proposal, wait for ref confirm."""
        team_usernames = {_normalize(p.username) for p in self.match.teams[team_index].players}

        def on_message(msg) -> None:
            if _normalize(getattr(msg.user, "username", "")) not in team_usernames:
                return
            pm = _find_map_by_input(self.match, msg.message)
            if pm is not None:
                self._pending_proposal = {
                    "step": step.name,
                    "team_index": team_index,
                    "map": pm.name or str(pm.beatmap_id),
                    "beatmap_id": pm.beatmap_id,
                }
                asyncio.ensure_future(self._push_state())

        self.lobby.channel.on("message", on_message)
        try:
            return await self._await_map_from_ref()
        finally:
            self.lobby.channel.remove_listener("message", on_message)
            self._pending_proposal = None

    async def await_pick(self, team_index: int) -> int | None:
        if self.mode == RefMode.ASSISTED:
            return await self._await_map_assisted(team_index, Step.PICK)
        if self.mode == RefMode.OFF:
            return await self._await_map_from_ref()
        return await self._await_map_choice(team_index)

    async def await_ban(self, team_index: int) -> int | None:
        if self.mode == RefMode.ASSISTED:
            return await self._await_map_assisted(team_index, Step.BAN)
        if self.mode == RefMode.OFF:
            return await self._await_map_from_ref()
        return await self._await_map_choice(team_index)

    async def await_protect(self, team_index: int) -> int | None:
        if self.mode == RefMode.ASSISTED:
            return await self._await_map_assisted(team_index, Step.PROTECT)
        if self.mode == RefMode.OFF:
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

    async def _pre_pick(self, team_index: int) -> None:
        """Called just before await_pick. Override to suppress or replace the pick timer."""
        if self.mode != RefMode.OFF:
            await self.announce_next_pick(team_index)
            await self.lobby.timer(self.timers.pick)

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

                team_index, step = self.next_step(self.match.match_status)

                if step == Step.WIN:
                    await self.announce_win(team_index)
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
            await self.lobby.close()

    async def play_map(self, beatmap_id: int, team_index: int, step: Step) -> None:
        """Set the map, wait for ready, start, wait for result, record it.

        If >abort is issued while the map is in progress the ready/start cycle
        repeats for the same map without recording a result or advancing logic.
        """
        pm = _find_map(self.match, beatmap_id)
        gamemode = self.match.ruleset.gamemode.value
        mods = pm.effective_mods() if pm else None

        await self.lobby.set_map(beatmap_id, gamemode)
        enforced = self.match.ruleset.enforced_mods
        extra = str(mods) if mods else ""
        base_mods = str(enforced) if enforced else ""
        combined = extra if "Freemod" in extra else (extra + base_mods)
        if combined:
            await self.lobby.set_mods(combined)

        self._map_in_progress = True
        try:
            while True:
                self._abort_event.clear()
                await self.lobby.timer(self.timers.between_maps)

                ready_t = asyncio.create_task(self.lobby.wait_for_all_ready())
                timer_t = asyncio.create_task(self.lobby.wait_for_timer())
                abort_t = asyncio.create_task(self._abort_event.wait())
                done, pending = await asyncio.wait(
                    {ready_t, timer_t, abort_t}, return_when=asyncio.FIRST_COMPLETED
                )
                for t in pending:
                    t.cancel()
                await asyncio.gather(*pending, return_exceptions=True)

                if abort_t in done:
                    await self.lobby.say("Map aborted. Waiting for everyone to ready up again.")
                    continue

                await self.lobby.start(delay=self.timers.force_start)

                result_t = asyncio.create_task(self.lobby.wait_for_match_end())
                abort_t2 = asyncio.create_task(self._abort_event.wait())
                done2, pending2 = await asyncio.wait(
                    {result_t, abort_t2}, return_when=asyncio.FIRST_COMPLETED
                )
                for t in pending2:
                    t.cancel()
                await asyncio.gather(*pending2, return_exceptions=True)

                if abort_t2 in done2:
                    await self.lobby.say("Map aborted. Waiting for everyone to ready up again.")
                    continue

                result = result_t.result()
                break
        finally:
            self._map_in_progress = False

        self.match.record_action(team_index, step, beatmap_id)
        return result
