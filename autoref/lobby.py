"""Lobby: thin wrapper around BanchoLobby for match orchestration."""
import asyncio
from dataclasses import dataclass, field

import bancho


@dataclass
class PlayerResult:
    username: str
    score: int
    passed: bool


@dataclass
class MatchResult:
    scores: list[PlayerResult] = field(default_factory=list)


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

    # ---------------------------------------------------------- room lifecycle

    async def create(self, name: str, private: bool = False) -> int:
        if private:
            # BanchoClient.make_lobby doesn't support private; send manually
            future: asyncio.Future = asyncio.get_event_loop().create_future()

            def on_pm(msg: bancho.PrivateMessage) -> None:
                if msg.user.username != "BanchoBot" or future.done():
                    return
                import re
                m = re.match(r"Created the tournament match https://osu\.ppy\.sh/mp/(\d+)", msg.message)
                if m:
                    future.set_result(int(m.group(1)))

            self._client.on("PM", on_pm)
            await self._client.send_message("BanchoBot", f"!mp makeprivate {name}")
            lobby_id = await future
            self._client.remove_listener("PM", on_pm)
            self._lobby = await self._client.join_lobby(lobby_id)
        else:
            self._lobby = await self._client.make_lobby(name)

        self._lobby.on("playerJoined", lambda d: self.players.add(d["player"].user.username))
        self._lobby.on("playerLeft", lambda p: self.players.discard(p.user.username))
        self._lobby.on("matchStarted", self._on_match_started)
        self._lobby.on("playerFinished", self._on_player_finished)
        self._lobby.on("matchFinished", self._on_match_finished)
        self._lobby.on("allPlayersReady", lambda: self._all_ready_event.set())
        self._lobby.on("timerEnded", lambda: self._timer_end_event.set())

        return self._lobby.id

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
        await self._lobby.close_lobby()

    # ----------------------------------------------------------- room settings

    async def set_map(self, beatmap_id: int, gamemode: int = 0) -> None:
        await self._lobby.set_map(beatmap_id, bancho.BanchoGamemode(gamemode))

    async def set_mods(self, mods: str) -> None:
        # Accept a string like "HD NF" or a Mod flag; parse via bancho enums if needed
        from bancho.lobby import _parse_mods
        parsed, freemod = _parse_mods(mods)
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
        await self._lobby.start_match(delay)

    async def abort(self) -> None:
        await self._lobby.abort_match()

    async def timer(self, seconds: int = 30) -> None:
        self._timer_end_event.clear()
        await self._lobby.start_timer(seconds)

    async def abort_timer(self) -> None:
        await self._lobby.abort_timer()

    async def say(self, msg: str) -> None:
        await self._lobby.channel.send_message(msg)

    # ------------------------------------------------------------ await events

    async def wait_for_match_end(self) -> MatchResult:
        await self._match_finished_event.wait()
        return self.last_result

    async def wait_for_all_ready(self) -> None:
        await self._all_ready_event.wait()

    async def wait_for_timer(self) -> None:
        await self._timer_end_event.wait()
