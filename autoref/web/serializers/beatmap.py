from ..schemas.beatmap import BeatmapResponse


def beatmap_to_response(meta: dict) -> BeatmapResponse:
    """Map raw beatmap cache dict to BeatmapResponse shape."""
    return BeatmapResponse(
        id=meta.get("id"),
        beatmapset_id=meta.get("beatmapset_id"),
        title=meta.get("title", ""),
        artist=meta.get("artist", ""),
        diff=meta.get("version", ""),
        len=meta.get("total_length", 0),
        stars=meta.get("stars", 0.0),
        ar=meta.get("ar", 0.0),
        od=meta.get("od", 0.0),
        cs=meta.get("cs", 0.0),
        hp=meta.get("hp", 0.0),
    )
