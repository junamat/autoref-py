"""AutoRef: drives a Match through its steps using a Lobby."""
import asyncio

import bancho

from .enums import Step
from .lobby import Lobby
from .models import Match, PlayableMap


def _find_map(match: Match, beatmap_id: int) -> PlayableMap | None:
    stack = list(match.pool.maps)
    while stack:
        item = stack.pop()
        from .models import Pool
        if isinstance(item, Pool):
            stack.extend(item.maps)
        elif item.beatmap_id == beatmap_id:
            return item
    return None


class AutoRef:
    """Orchestrates a Match by calling next_step in a loop and acting on the Lobby."""

    def __init__(self, client: bancho.BanchoClient, match: Match, room_name: str):
        self._client = client
        self.match = match
        self.room_name = room_name
        self.lobby = Lobby(client)

    async def run(self) -> None:
        ruleset = self.match.ruleset

        await self.lobby.create(self.room_name)
        await self.lobby.set_room(
            team_mode=2,  # TeamVs
            score_mode=ruleset.win_condition.value - 1,  # WinCondition enum offset
            size=ruleset.vs * 2,
        )
        if ruleset.enforced_mods:
            await self.lobby.set_mods(str(ruleset.enforced_mods))

        for team in self.match.teams:
            for player in team.players:
                await self.lobby.invite(player.username)

        while True:
            team_index, step = self.match.next_step(self.match.match_status)

            if step == Step.WIN:
                break

            if step in (Step.PICK, Step.BAN, Step.PROTECT):
                # Caller's next_step must encode the chosen beatmap_id somehow;
                # here we expect it to return a 3-tuple when a map is involved.
                # For flexibility, next_step may return (team_index, step, beatmap_id).
                raise NotImplementedError(
                    "next_step must return (team_index, step, beatmap_id) for PICK/BAN/PROTECT"
                )

            await asyncio.sleep(0)  # yield

        await self.lobby.close()

    async def play_map(self, beatmap_id: int, team_index: int, step: Step) -> None:
        """Set the map, wait for all ready, start, wait for result, record it."""
        pm = _find_map(self.match, beatmap_id)
        gamemode = self.match.ruleset.gamemode.value

        await self.lobby.set_map(beatmap_id, gamemode)

        if pm and pm.mods:
            await self.lobby.set_mods(str(pm.mods))

        await self.lobby.wait_for_all_ready()
        await self.lobby.start()
        result = await self.lobby.wait_for_match_end()

        self.match.record_action(team_index, step, beatmap_id)
        return result
