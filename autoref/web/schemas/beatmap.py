from typing import TypedDict


class BeatmapResponse(TypedDict):
    id: int | None
    beatmapset_id: int | None
    title: str
    artist: str
    diff: str
    len: int
    stars: float
    ar: float
    od: float
    cs: float
    hp: float
