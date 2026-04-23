from collections.abc import Callable
from pathlib import Path
import asyncio

import aiosu
import pandas as pd

from .enums import WinCondition, Step
from .client import make_client


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
        self.name = name  # map code used in picks/bans, e.g. "NM1", "HD2", "TB"

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
    def __init__(self, name: str, *maps: "Pool | PlayableMap"):
        self.name = name
        self.maps = list(maps)


class ModdedPool(Pool):
    def __init__(self, name: str, mods: aiosu.models.mods.Mods, *maps: "Pool | PlayableMap"):
        super().__init__(name, *maps)
        self.mods = mods


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
    ):
        self.vs = vs
        self.gamemode = gamemode
        self.win_condition = win_condition
        self.enforced_mods = aiosu.models.mods.Mods(enforced_mods)


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
