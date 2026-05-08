from __future__ import annotations

import aiosu

from ..enums import MapState, WinCondition

NO_MODS = object()  # sentinel: explicitly no extra mods, bypasses pool/name inference

# Extra mods only — NF excluded because applied room-wide via Ruleset.enforced_mods.
_MOD_INFERENCE: dict[str, str] = {
    "HD": "HD",
    "HR": "HR",
    "DT": "DT",
    "FM": "Freemod",
}


class PlayableMap:
    def __init__(
        self,
        beatmap_id: int,
        mods: aiosu.models.mods.Mods | None = None,
        win_condition: WinCondition = WinCondition.INHERIT,
        name: str | None = None,
        is_tiebreaker: bool = False,
        score_multipliers: dict[str, float] | None = None,
    ):
        self.beatmap_id = beatmap_id
        self.beatmap: aiosu.models.Beatmap | None = None
        self.mods = mods
        self.win_condition = win_condition
        self.name = name
        self.is_tiebreaker = is_tiebreaker
        self.score_multipliers = score_multipliers
        self.state = MapState.PICKABLE
        self._pool_mult_chain: list[dict[str, float]] = []
        self._pool_mods: aiosu.models.mods.Mods | None = None

    def effective_multipliers(self, ruleset_mults: dict[str, float] | None = None) -> dict[str, float]:
        """Resolve effective multiplier table: ruleset → pool chain → map. Most-specific wins."""
        from ..utils.math import merge_multipliers
        return merge_multipliers(ruleset_mults, *self._pool_mult_chain, self.score_multipliers)

    def effective_mods(self, pool_mods: aiosu.models.mods.Mods | None = None):
        """Resolve extra mods: explicit (or NO_MODS) > pool_mods > name inference."""
        if self.mods is NO_MODS:
            return None
        if self.mods is not None:
            return self.mods
        pm = pool_mods if pool_mods is not None else getattr(self, "_pool_mods", None)
        if pm is NO_MODS:
            return None
        if pm is not None:
            return pm
        if self.name:
            prefix = self.name[:2].upper()
            inferred = _MOD_INFERENCE.get(prefix)
            if inferred:
                return aiosu.models.mods.Mods(inferred)
        return None

    @classmethod
    async def create(
        cls,
        beatmap_id: int,
        mods: aiosu.models.mods.Mods | None = None,
        win_condition: WinCondition = WinCondition.INHERIT,
        name: str | None = None,
        is_tiebreaker: bool = False,
        client: "aiosu.v2.Client | None" = None,
    ) -> "PlayableMap":
        instance = cls(beatmap_id, mods, win_condition, name, is_tiebreaker)
        if client is not None:
            instance.beatmap = await client.get_beatmap(beatmap_id)
        else:
            from ...client import make_client
            async with make_client() as c:
                instance.beatmap = await c.get_beatmap(beatmap_id)
        return instance
