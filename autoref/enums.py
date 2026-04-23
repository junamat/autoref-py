from enum import Enum


class WinCondition(Enum):
    INHERIT = 0
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


class MapState(Enum):
    INHERIT = 0
    PICKABLE = 1
    PROTECTED = 2
    BANNED = 3
    DISALLOWED = 4
    OTHER = 11


class Step(Enum):
    PICK = 1
    BAN = 2
    PROTECT = 3
    WIN = 4
    OTHER = 11
