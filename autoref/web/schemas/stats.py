from typing import Any, TypedDict


class BestScore(TypedDict):
    beatmap_id: int
    name: str | None
    score: int
    accuracy: float
    rank: str | None
    mods: list[Any]


class LeaderboardRow(TypedDict, total=False):
    user_id: int
    username: str
    maps_played: int
    avg_score: int
    avg_acc: float
    best: BestScore


class MapPoolRow(TypedDict, total=False):
    beatmap_id: int
    name: str | None
    pool_order: int
    picks: int
    bans: int
    protects: int
    protects_picked: int
    protects_unused: int
    avg_score: int | None
    avg_acc: float | None
    mods: list[str]
    pool_mod: str
    play_count: int
    artist: str
    title: str
    version: str
