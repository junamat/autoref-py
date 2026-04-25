"""QualifiersAutoRef: plays every map in pool order, no picks/bans, supports multiple runs."""
import asyncio

import bancho

from .autoref import AutoRef
from .beatmap_cache import BeatmapCache
from .enums import RefMode, Step
from .models import Match, Timers


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

    async def await_pick(self, team_index: int) -> int:
        if self.mode in (RefMode.ASSISTED, RefMode.OFF):
            # Ref confirms advance with >next (args ignored; pool order is fixed).
            self._next_future = asyncio.get_event_loop().create_future()
            try:
                await self._next_future
            finally:
                self._next_future = None

        pm = self._maps[self._map_index]
        self._map_index += 1
        if self._map_index >= len(self._maps) and self._run_index + 1 < self.runs:
            self._run_index += 1
            self._map_index = 0
        return pm.beatmap_id

    async def _pre_pick(self, team_index: int) -> None:
        await self.announce_next_pick(team_index)
        # no pick timer — next map is predetermined, nothing to wait for

    async def handle_other(self, team_index: int) -> None:
        pass  # qualifiers has no OTHER steps

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
        overhead = self.timers.between_maps + self.timers.force_start
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
        state["events"]         = []   # mappool grid already shows per-map state
        state["phase"]          = f"run {self._run_index + 1}/{self.runs}" if self.runs > 1 else None
        return state
