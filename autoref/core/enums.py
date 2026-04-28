from enum import Enum


class WinCondition(Enum):
    # 0-3 map directly to BanchoLobbyWinConditions
    SCORE_V1       = 0
    ACCURACY       = 1
    COMBO          = 2
    SCORE_V2       = 3
    # custom — require AutoRef subclass logic, not sent to bancho directly
    INHERIT        = -1
    FEWER_MISSES   = 4
    TARGET_SCORE   = 5
    TARGET_ACCURACY = 6
    OTHER          = 11


class MapState(Enum):
    INHERIT    = -1  # inherit state from parent pool
    PICKABLE   = 0
    PROTECTED  = 1
    BANNED     = 2
    DISALLOWED = 3
    PLAYED     = 4
    OTHER      = 11


class Step(Enum):
    PICK    = 0
    BAN     = 1
    PROTECT = 2
    FINISH  = 3
    OTHER   = 11


class RefMode(Enum):
    OFF      = "off"
    ASSISTED = "assisted"
    AUTO     = "auto"
