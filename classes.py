from collections.abc import Callable

from dotenv import load_dotenv
from os import getenv
import aiosu
from enum import Enum
import pandas as pd
import asyncio

load_dotenv()

class WinCondition(Enum):
    SCORE_V2 = 1
    ACCURACY_V2 = 2
    COMBO = 3
    FEWER_MISSES = 4
    TARGET_SCORE_V2 = 5
    TARGET_ACCURACY_V2 = 6
    SCORE_V1 = 7
    ACCURACY_V1 = 8
    TARGET_SCORE_V1 = 9
    TARGET_ACCURACY_V1 = 10
    OTHER = 11

class Step(Enum):
    PICK = 1
    BAN = 2
    PROTECT = 3
    OTHER = 11

def make_client() -> aiosu.v2.Client:
    return aiosu.v2.Client(
        client_id = getenv("CLIENT_ID"),
        client_secret = getenv("CLIENT_SECRET"),
    )


class PlayableMap:
    def __init__(
        self,
        beatmap_id: int,
        mods: aiosu.models.mods.Mods = None,
        win_condition: WinCondition = WinCondition.SCORE_V2,
        comment: str = None,
    ):
        self.beatmap_id = beatmap_id
        self.beatmap = None
        self.mods = mods
        self.win_condition = win_condition
        self.comment = comment

    @classmethod
    async def create(
        cls,
        beatmap_id: int,
        mods: aiosu.models.mods.Mods = None,
        win_condition: WinCondition = WinCondition.SCORE_V2,
        comment: str = None,
    ) -> "PlayableMap":
        instance = cls(beatmap_id, mods, win_condition, comment)
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
    def __init__(self, vs: int, gamemode: aiosu.models.Gamemode, enforced_nf: bool = True, pipeline: MatchPipeline = None):
        self.vs = vs
        self.gamemode = gamemode
        self.enforced_nf = enforced_nf
        self.pipeline = pipeline

class Match:
    def __init__(self, ruleset: Ruleset, pool: Pool, next_step: Callable[[pd.DataFrame], (int, Step)], *teams: Team): #next_step(match_status) returns (team_index, Step)
        self.ruleset = ruleset
        self.pool = pool
        self.next_step = next_step
        self.teams = teams


async def main():
    team = await Team.create("equipo", 2)
    print(team.to_dataframe())

    map1 = await PlayableMap.create(75, mods=aiosu.models.mods.Mods("HD"))
    print(map1.beatmap)


if __name__ == "__main__":
    asyncio.run(main())