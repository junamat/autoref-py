import aiosu
from enum import Enum

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

class PlayableMap:
    def __init__(self, beatmap: aiosu.models.beatmap.Beatmap,
                  mods: aiosu.models.mods.Mods = None, win_condition: WinCondition = WinCondition.SCORE_V2,
                  comment: str = None):
        self.beatmap = beatmap
        self.mods = mods
        self.win_condition = win_condition
        self.comment = comment

class Pool:
    def __init__(self, name: str, maps: list[PlayableMap] | list[Pool]):
        self.name = name
        self.maps = maps

class ModdedPool(Pool):
    def __init__(self, name: str, maps: list[PlayableMap] | list[Pool], mods: aiosu.models.mods.Mods):
        super().__init__(name, maps)
        self.mods = mods

class Team:
    def __init__(self, name: str, players: list[aiosu.models.user.User]):
        self.name = name
        self.players = players

class Ruleset:
    def __init__(self, vs: int, gamemode: aiosu.models.Gamemode, enforced_nf: bool, ):