from __future__ import annotations

from collections.abc import Callable

import aiosu

from .playable_map import PlayableMap


class Pool:
    def __init__(self, name: str, *maps: "Pool | PlayableMap",
                 order: "Callable[[list[PlayableMap]], list[PlayableMap]] | None" = None,
                 score_multipliers: dict[str, float] | None = None):
        self.name = name
        self.maps = list(maps)
        self.order = order
        self.score_multipliers = score_multipliers

    def flatten(self, _pool_mods=None, _mult_chain: list | None = None) -> list[PlayableMap]:
        """Depth-first flatten, propagating pool mods, multiplier chain, and order."""
        chain = list(_mult_chain or [])
        if self.score_multipliers:
            chain = chain + [self.score_multipliers]
        result = []
        for item in self.maps:
            if isinstance(item, Pool):
                result.extend(item.flatten(_pool_mods=_pool_mods, _mult_chain=chain))
            else:
                pm = PlayableMap(item.beatmap_id, item.mods, item.win_condition,
                                 item.name, item.is_tiebreaker,
                                 score_multipliers=item.score_multipliers)
                pm.beatmap = item.beatmap
                pm._pool_mods = _pool_mods
                pm._pool_mult_chain = chain
                result.append(pm)
        if self.order:
            result = self.order(result)
        return result


class ModdedPool(Pool):
    def __init__(self, name: str, mods: aiosu.models.mods.Mods, *maps: "Pool | PlayableMap",
                 order=None, score_multipliers: dict[str, float] | None = None):
        super().__init__(name, *maps, order=order, score_multipliers=score_multipliers)
        self.mods = mods

    def flatten(self, _pool_mods=None, _mult_chain: list | None = None) -> list[PlayableMap]:
        return super().flatten(_pool_mods=self.mods, _mult_chain=_mult_chain)
