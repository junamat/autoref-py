"""Lobby: thin wrapper around BanchoLobby for match orchestration."""
import asyncio
import logging
import sys
from dataclasses import dataclass, field

import bancho

logger = logging.getLogger(__name__)


@dataclass
class PlayerResult:
    username: str
    score: int
    passed: bool


@dataclass
class MatchResult:
    scores: list[PlayerResult] = field(default_factory=list)


@dataclass
class SlotInfo:
    username: str
    ready: bool
    user_id: int
    team: str | None   # "Blue", "Red", or None
    is_host: bool


class Lobby:
    """Manages a single !mp room via BanchoClient."""

    def __init__(self, client: bancho.BanchoClient):
        self._client = client
        self._lobby: bancho.BanchoLobby | None = None

        self._match_finished_event = asyncio.Event()
        self._all_ready_event = asyncio.Event()
        self._timer_end_event = asyncio.Event()

        self.last_result: MatchResult | None = None
        self.players: set[str] = set()
        self.slot_info: list[SlotInfo] = []
        self._message_hooks: list = []
        self._input_hooks: list = []
        self._output_sinks: list = []
        self._reply_sinks: dict = {}
        self._presence_hooks: list = []

    def add_message_hook(self, fn) -> None:
        self._message_hooks.append(fn)

    def add_input_hook(self, fn) -> None:
        """Hook called for every CLI/web input line. Return True to consume, False to pass through to chat."""
        self._input_hooks.append(fn)

    def add_presence_hook(self, fn) -> None:
        """Register an async callable() called whenever a player joins or leaves."""
        self._presence_hooks.append(fn)

    def add_output_sink(self, fn) -> None:
        """Register an async callable(text: str) called for every message the bot sends."""
        self._output_sinks.append(fn)

    def register_reply_sink(self, source: str, fn) -> None:
        """Register an async callable(text: str) as the reply channel for a named source.

        When AutoRef calls lobby.reply(text, source), the registered sink is used
        instead of broadcasting to the Bancho lobby.  Useful for sending ref-only
        output (e.g. >help) to CLI stdout, a Discord DM, or a web panel without
        cluttering the match room.
        """
        self._reply_sinks[source] = fn

    async def reply(self, text: str, source: str) -> None:
        """Send text back to the originating source only.

        Falls back to lobby.say() when no sink is registered for that source
        (e.g. a Bancho username that typed a command in chat).
        """
        sink = self._reply_sinks.get(source)
        if sink:
            try:
                await sink(text)
            except Exception:
                logger.exception("reply sink error for source %r", source)
        else:
            await self.say(text)

    async def handle_input(self, text: str, source: str = "cli") -> None:
        """Route a line of text from CLI/web through input hooks, falling back to say()."""
        for fn in self._input_hooks:
            if await fn(text, source):
                return
        await self.say(text)

    @property
    def channel(self) -> bancho.BanchoLobbyChannel:
        assert self._lobby is not None
        return self._lobby.channel

    @property
    def room_id(self) -> int | None:
        return self._lobby.id if self._lobby else None

    # ---------------------------------------------------------- room lifecycle

    async def create(self, name: str, private: bool = False) -> int:
        self._lobby = await self._client.make_lobby(name, private=private)

        def _on_joined(d):
            self.players.add(d["player"].user.username)
            for fn in self._presence_hooks:
                asyncio.ensure_future(fn())

        def _on_left(p):
            self.players.discard(p.user.username)
            for fn in self._presence_hooks:
                asyncio.ensure_future(fn())

        self._lobby.on("playerJoined", _on_joined)
        self._lobby.on("playerLeft", _on_left)
        self._lobby.on("matchStarted", self._on_match_started)
        self._lobby.on("playerFinished", self._on_player_finished)
        self._lobby.on("matchFinished", self._on_match_finished)
        self._lobby.on("allPlayersReady", lambda: self._all_ready_event.set())
        self._lobby.on("timerEnded", lambda: self._timer_end_event.set())
        self._lobby.channel.on("message", self._on_channel_message)

        return self._lobby.id

    def _on_channel_message(self, msg) -> None:
        logger.info("[%s] %s", msg.user.username, msg.message)
        for fn in self._message_hooks:
            asyncio.ensure_future(fn(msg.user.username, msg.message, False))

    def _on_match_started(self) -> None:
        self._match_finished_event.clear()
        self.last_result = MatchResult()

    def _on_player_finished(self, score: bancho.BanchoLobbyPlayerScore) -> None:
        if self.last_result is not None:
            self.last_result.scores.append(
                PlayerResult(score.player.user.username, score.score, score.passed)
            )

    def _on_match_finished(self, scores: list) -> None:
        self._match_finished_event.set()

    async def close(self) -> None:
        logger.info("closing lobby")
        await self._lobby.close_lobby()

    # ----------------------------------------------------------- room settings

    async def set_map(self, beatmap_id: int, gamemode: int = 0) -> None:
        await self._lobby.set_map(beatmap_id, bancho.BanchoGamemode(gamemode))

    async def set_mods(self, mods: str) -> None:
        from bancho.lobby import _parse_mods
        # aiosu Mods.__str__ returns concatenated e.g. "HDNF" — insert spaces between known abbrevs
        import re
        spaced = re.sub(r'([A-Z]{2})', r'\1 ', mods).strip()
        parsed, freemod = _parse_mods(spaced)
        await self._lobby.set_mods(parsed, freemod)

    async def set_room(self, team_mode: int, score_mode: int, size: int | None = None) -> None:
        await self._lobby.set_settings(
            bancho.BanchoLobbyTeamModes(team_mode),
            bancho.BanchoLobbyWinConditions(score_mode),
            size,
        )

    async def set_title(self, name: str) -> None:
        await self._lobby.set_name(name)

    async def set_password(self, password: str = "") -> None:
        if password:
            await self._lobby.set_password(password)
        else:
            await self._lobby.clear_password()

    # ------------------------------------------------------------ player mgmt

    async def invite(self, username: str) -> None:
        await self._lobby.invite_player(username)

    async def kick(self, username: str) -> None:
        await self._lobby.kick_player(username)

    async def move(self, username: str, slot: int) -> None:
        await self._lobby.move_player(username, slot)

    async def set_team(self, username: str, colour: str) -> None:
        team = bancho.BanchoLobbyTeams.Red if colour.lower() == "red" else bancho.BanchoLobbyTeams.Blue
        await self._lobby.change_team(username, team)

    async def add_ref(self, username: str) -> None:
        await self._lobby.add_ref(username)

    # -------------------------------------------------------------- match flow

    async def start(self, delay: int | None = None) -> None:
        self._all_ready_event.clear()
        self._match_finished_event.clear()
        await self._lobby.start_match(delay)

    async def abort(self) -> None:
        await self._lobby.abort_match()

    async def timer(self, seconds: int = 30) -> None:
        self._timer_end_event.clear()
        await self._lobby.start_timer(seconds)

    async def abort_timer(self) -> None:
        await self._lobby.abort_timer()

    async def fetch_settings(self, timeout: float = 5.0) -> list[SlotInfo]:
        """Send !mp settings and wait for BanchoBot's response."""
        from bancho.enums import BanchoLobbyPlayerStates, BanchoLobbyTeams
        
        players = await self._lobby.fetch_settings(timeout=timeout)
        slots: list[SlotInfo] = []
        for p in players:
            if p is not None:
                team = None
                if p.team == BanchoLobbyTeams.Blue:
                    team = "Blue"
                elif p.team == BanchoLobbyTeams.Red:
                    team = "Red"

                slots.append(SlotInfo(
                    username=p.user.username,
                    ready=p.state == BanchoLobbyPlayerStates.Ready,
                    user_id=getattr(p.user, "id", 0),
                    team=team,
                    is_host=p.is_host,
                ))
        self.slot_info = slots
        return self.slot_info

    async def say(self, msg: str) -> None:
        logger.info("[autoref] %s", msg)
        await self._lobby.channel.send_message(msg)
        for fn in self._message_hooks:
            await fn("autoref", msg, True)
        for fn in self._output_sinks:
            try:
                await fn(msg)
            except Exception:
                logger.exception("output sink error")

    # ------------------------------------------------------------ await events

    async def wait_for_match_end(self) -> MatchResult:
        await self._match_finished_event.wait()
        return self.last_result

    async def wait_for_all_ready(self) -> None:
        await self._all_ready_event.wait()

    async def wait_for_timer(self) -> None:
        await self._timer_end_event.wait()

    # ---------------------------------------------------------- cli passthrough

    async def run_cli_input(self) -> None:
        """Read lines from stdin and forward them to the lobby channel."""
        loop = asyncio.get_event_loop()
        reader = asyncio.StreamReader()
        transport, _ = await loop.connect_read_pipe(
            lambda: asyncio.StreamReaderProtocol(reader), sys.stdin
        )

        async def _cli_reply(text: str) -> None:
            print(text)

        self.register_reply_sink("cli", _cli_reply)
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                text = line.decode().rstrip("\n")
                if text:
                    await self.handle_input(text, "cli")
        finally:
            transport.close()
