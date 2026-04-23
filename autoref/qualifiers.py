"""QualifiersAutoRef: plays every map in pool order, no picks/bans, supports multiple runs."""
import bancho

from .autoref import AutoRef
from .enums import Step
from .models import Match, Timers


class QualifiersAutoRef(AutoRef):
    """Plays the full pool sequentially, N times. No picks, bans, or protects."""

    def __init__(self, client: bancho.BanchoClient, match: Match, room_name: str,
                 runs: int = 1, timers: Timers | None = None):
        super().__init__(client, match, room_name, timers)
        self.runs = runs
        self._maps = match.pool.flatten()
        self._map_index = 0
        self._run_index = 0

    def next_step(self, match_status) -> tuple[int, Step]:
        if self._map_index < len(self._maps):
            return (0, Step.PICK)
        return (0, Step.WIN)

    async def await_pick(self, team_index: int) -> int:
        pm = self._maps[self._map_index]
        self._map_index += 1
        if self._map_index >= len(self._maps) and self._run_index + 1 < self.runs:
            self._run_index += 1
            self._map_index = 0
        return pm.beatmap_id

    async def handle_other(self, team_index: int) -> None:
        pass  # qualifiers has no OTHER steps

    async def announce_next_pick(self, team_index: int) -> None:
        pm = self._maps[self._map_index]
        name = pm.name or str(pm.beatmap_id)
        await self.lobby.say(f"Next map: {name}")
