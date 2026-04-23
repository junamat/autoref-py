from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
import asyncio

import aiosu
import pandas as pd

from .enums import WinCondition, MapState, Step
from .client import make_client


@dataclass
class Timers:
    pick: int = 120        # seconds a team has to pick
    ban: int = 120         # seconds a team has to ban
    protect: int = 120     # seconds a team has to protect
    ready_up: int = 120    # seconds players have to ready up after map is set
    force_start: int = 10  # seconds before force-starting when ready timer expires
    between_maps: int = 10 # seconds between maps


_MOD_INFERENCE: dict[str, str] = {
    "NM": "NF",
    "HD": "HDNF",
    "HR": "HRNF",
    "DT": "DTNF",
    "FM": "Freemod",
    "TB": "NF",
}


class PlayableMap:
    def __init__(
        self,
        beatmap_id: int,
        mods: aiosu.models.mods.Mods = None,
        win_condition: WinCondition = WinCondition.INHERIT,
        name: str = None,
    ):
        self.beatmap_id = beatmap_id
        self.beatmap = None
        self.mods = mods
        self.win_condition = win_condition
        self.name = name
        self.state = MapState.PICKABLE

    def effective_mods(self, pool_mods: aiosu.models.mods.Mods = None) -> aiosu.models.mods.Mods | None:
        """Resolve mods with priority: explicit > pool_mods > name inference."""
        if self.mods is not None:
            return self.mods
        pm = pool_mods if pool_mods is not None else getattr(self, "_pool_mods", None)
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
        mods: aiosu.models.mods.Mods = None,
        win_condition: WinCondition = WinCondition.INHERIT,
        name: str = None,
    ) -> "PlayableMap":
        instance = cls(beatmap_id, mods, win_condition, name)
        async with make_client() as client:
            instance.beatmap = await client.get_beatmap(beatmap_id)
        return instance


class Pool:
    def __init__(self, name: str, *maps: "Pool | PlayableMap",
                 order: "Callable[[list[PlayableMap]], list[PlayableMap]] | None" = None):
        self.name = name
        self.maps = list(maps)
        self.order = order  # optional callable to reorder the flattened list

    def flatten(self, _pool_mods=None) -> "list[PlayableMap]":
        """Depth-first flatten, propagating pool mods and applying order."""
        result = []
        for item in self.maps:
            if isinstance(item, Pool):
                result.extend(item.flatten(_pool_mods=_pool_mods))
            else:
                pm = PlayableMap(item.beatmap_id, item.mods, item.win_condition, item.name)
                pm.beatmap = item.beatmap
                pm._pool_mods = _pool_mods
                result.append(pm)
        if self.order:
            result = self.order(result)
        return result


class ModdedPool(Pool):
    def __init__(self, name: str, mods: aiosu.models.mods.Mods, *maps: "Pool | PlayableMap",
                 order=None):
        super().__init__(name, *maps, order=order)
        self.mods = mods

    def flatten(self, _pool_mods=None) -> "list[PlayableMap]":
        # own mods take priority over parent pool mods
        return super().flatten(_pool_mods=self.mods)


class Team:
    def __init__(self, name: str):
        self.name = name
        self.players: list = []

    @classmethod
    async def create(cls, name: str, *player_ids: int) -> "Team":
        instance = cls(name)
        async with make_client() as client:
            results = await asyncio.gather(
                *(client.get_user(pid) for pid in player_ids)
            )
        instance.players = list(results)
        return instance

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([vars(p) for p in self.players])


class Ruleset:
    def __init__(
        self,
        vs: int,
        gamemode: aiosu.models.Gamemode,
        win_condition: WinCondition = WinCondition.SCORE_V2,
        enforced_mods: str = "NF",
        team_mode: int = 2,  # 0=HeadToHead, 2=TeamVs
    ):
        self.vs = vs
        self.gamemode = gamemode
        self.win_condition = win_condition
        self.enforced_mods = aiosu.models.mods.Mods(enforced_mods) if enforced_mods else None
        self.team_mode = team_mode


class Match:
    _STATUS_COLUMNS = ["turn", "team_index", "step", "beatmap_id", "timestamp"]

    def __init__(
        self,
        ruleset: Ruleset,
        pool: Pool,
        next_step: Callable[[pd.DataFrame], tuple[int, Step]],
        *teams: Team,
    ):
        self.ruleset = ruleset
        self.pool = pool
        self.next_step = next_step  # next_step(match_status) -> (team_index, Step)
        self.teams = teams
        self.match_status = pd.DataFrame(columns=self._STATUS_COLUMNS)
        self.match_id: int | None = None  # assigned by MatchDatabase after persisting

    def record_action(self, team_index: int, step: Step, beatmap_id: int) -> None:
        row = {
            "turn": len(self.match_status),
            "team_index": team_index,
            "step": step.name,
            "beatmap_id": beatmap_id,
            "timestamp": pd.Timestamp.now(),
        }
        self.match_status = pd.concat(
            [self.match_status, pd.DataFrame([row])],
            ignore_index=True,
        )

    def save(self, path: str | Path) -> None:
        self.match_status.to_csv(path, index=False)

    def resume(self, path: str | Path) -> None:
        self.match_status = pd.read_csv(path, parse_dates=["timestamp"])
