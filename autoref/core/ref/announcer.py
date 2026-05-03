"""Announcer: default lobby chat announcements for pick/ban/protect events.

Swap by replacing `ref.announcer` with a custom subclass (e.g., DiscordAnnouncer).
"""
from ..lobby import Lobby
from ..models import Match, Timers
from ..utils import find_map as _find_map


class Announcer:
    def __init__(self, lobby: Lobby, match: Match, timers: Timers):
        self.lobby = lobby
        self.match = match
        self.timers = timers

    def _map_name(self, beatmap_id: int) -> str:
        pm = _find_map(self.match, beatmap_id)
        return pm.name if pm and pm.name else str(beatmap_id)

    async def pick(self, team_index: int, beatmap_id: int) -> None:
        team = self.match.teams[team_index]
        await self.lobby.say(f"{team.name} picked {self._map_name(beatmap_id)}")

    async def ban(self, team_index: int, beatmap_id: int) -> None:
        team = self.match.teams[team_index]
        await self.lobby.say(f"{team.name} banned {self._map_name(beatmap_id)}")

    async def protect(self, team_index: int, beatmap_id: int) -> None:
        team = self.match.teams[team_index]
        await self.lobby.say(f"{team.name} protected {self._map_name(beatmap_id)}")

    async def finish(self, team_index: int | None) -> None:
        if team_index is not None and 0 <= team_index < len(self.match.teams):
            await self.lobby.say(
                f"Match finished — {self.match.teams[team_index].name} wins!"
            )
        else:
            await self.lobby.say("Match closed.")

    async def closing(self) -> None:
        await self.lobby.say(f"Lobby closing in {self.timers.closing}s.")

    async def next_pick(self, team_index: int) -> None:
        await self.lobby.say(
            f"{self.match.teams[team_index].name}, you have {self.timers.pick}s to pick a map."
        )

    async def next_ban(self, team_index: int) -> None:
        await self.lobby.say(
            f"{self.match.teams[team_index].name}, you have {self.timers.ban}s to ban a map."
        )

    async def next_protect(self, team_index: int) -> None:
        await self.lobby.say(
            f"{self.match.teams[team_index].name}, you have {self.timers.protect}s to protect a map."
        )
