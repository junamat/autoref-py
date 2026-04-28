"""QualifiersAutoRef: plays every map in pool order, no picks/bans, supports multiple runs."""
import asyncio

import bancho

from ..core.base import AutoRef
from ..core.beatmap_cache import BeatmapCache
from ..core.enums import RefMode, Step
from ..core.models import Match, Timers


class QualifiersAutoRef(AutoRef):
    """Plays the full pool sequentially, N times. No picks, bans, or protects."""

    def __init__(self, client: bancho.BanchoClient, match: Match, room_name: str,
                 runs: int = 1, timers: Timers | None = None,
                 beatmap_cache: BeatmapCache | None = None, **kwargs):
        super().__init__(client, match, room_name, timers, **kwargs)
        self.runs = runs
        self._maps = match.pool.flatten()
        self._map_index = 0
        self._run_index = 0
        self._beatmap_cache: BeatmapCache = beatmap_cache or BeatmapCache()

    def next_step(self, match_status) -> tuple[int, Step]:
        if self._map_index < len(self._maps):
            return (0, Step.PICK)
        return (0, Step.WIN)

    async def _pre_loop(self) -> None:
        ids = [pm.beatmap_id for pm in self._maps]
        await self._beatmap_cache.prefetch(ids)

    async def await_pick(self, team_index: int) -> int | None:
        if self.mode in (RefMode.ASSISTED, RefMode.OFF):
            # Ref confirms advance with >next (args ignored; pool order is fixed).
            self._next_future = asyncio.get_event_loop().create_future()
            close_task = asyncio.ensure_future(self._close_event.wait())
            try:
                done, _ = await asyncio.wait(
                    {self._next_future, close_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
            finally:
                self._next_future = None
                close_task.cancel()
            if self._close_event.is_set():
                return None

        if self._close_event.is_set():
            return None

        pm = self._maps[self._map_index]
        self._map_index += 1
        if self._map_index >= len(self._maps) and self._run_index + 1 < self.runs:
            self._run_index += 1
            self._map_index = 0
        return pm.beatmap_id

    async def _pre_pick(self, team_index: int) -> None:
        await self.announce_next_pick(team_index)
        # no pick timer — next map is predetermined, nothing to wait for

    async def announce_pick(self, team_index: int, beatmap_id: int) -> None:
        pass

    async def announce_next_pick(self, team_index: int) -> None:
        pm = self._maps[self._map_index]
        name = pm.name or str(pm.beatmap_id)
        await self.lobby.say(f"Next map: {name}")

    # ---------------------------------------------------------------- state

    def _get_state(self) -> dict:
        state = super()._get_state()

        total_per_run = len(self._maps)
        total_played  = self._run_index * total_per_run + self._map_index
        total_maps    = self.runs * total_per_run
        maps_remaining = total_maps - total_played

        # ETA: sum lengths of remaining maps + per-map overhead
        overhead = self.timers.ready_up + self.timers.start_map
        eta = 0

        def _map_eta(pm) -> int:
            meta = self._beatmap_cache.get(pm.beatmap_id)
            return (meta["total_length"] if meta else 0) + overhead

        # remainder of current run
        for pm in self._maps[self._map_index:]:
            eta += _map_eta(pm)
        # full remaining runs
        for _ in range(self._run_index + 1, self.runs):
            for pm in self._maps:
                eta += _map_eta(pm)

        # Build per-map info list (ordered, overrides base maps list)
        maps_list = []
        for i, pm in enumerate(self._maps):
            meta = self._beatmap_cache.get(pm.beatmap_id)
            if i < self._map_index:
                map_state = "played"
            elif i == self._map_index:
                map_state = "current"
            else:
                map_state = "upcoming"
            maps_list.append({
                "code":   pm.name or str(pm.beatmap_id),
                "state":  map_state,
                "tb":     False,
                "length": meta["total_length"] if meta else None,
                "title":  meta["title"]        if meta else None,
                "artist": meta["artist"]       if meta else None,
            })

        state["qualifier"]      = True
        state["maps"]           = maps_list
        state["maps_played"]    = total_played
        state["maps_remaining"] = maps_remaining
        state["total_maps"]     = total_maps
        state["eta_seconds"]    = eta
        state["run_index"]      = self._run_index
        state["runs"]           = self.runs
        state["events"]         = []

        # current map name for the landing card step badge
        current_name = None
        if self._map_index < len(self._maps):
            pm = self._maps[self._map_index]
            current_name = pm.name or str(pm.beatmap_id)

        if self.runs > 1:
            state["phase"] = f"{current_name} · run {self._run_index + 1}/{self.runs}" if current_name else f"run {self._run_index + 1}/{self.runs}"
        else:
            state["phase"] = current_name
        return state
