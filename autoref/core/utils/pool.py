from autoref.core.models import Match, Pool, PlayableMap
from autoref.core.enums import MapState

def normalize_name(name: str) -> str:
    return name.replace(" ", "_").casefold()

def find_map(match: "Match", beatmap_id: int) -> "PlayableMap | None":
    stack = list(match.pool.maps)
    while stack:
        item = stack.pop()
        if isinstance(item, Pool):
            stack.extend(item.maps)
        elif item.beatmap_id == beatmap_id:
            return item
    return None

def find_map_by_input(match: "Match", text: str) -> "PlayableMap | None":
    """Find a map by name/code. Only returns PICKABLE maps (ban path)."""
    needle = normalize_name(text)
    stack = list(match.pool.maps)
    while stack:
        item = stack.pop()
        if isinstance(item, Pool):
            stack.extend(item.maps)
        elif item.name and normalize_name(item.name) == needle:
            if item.state == MapState.PICKABLE:
                return item
    return None

def find_map_by_input_pick(match: "Match", text: str) -> "PlayableMap | None":
    """Like find_map_by_input but also allows PROTECTED maps (pick/protect path)."""
    needle = normalize_name(text)
    stack = list(match.pool.maps)
    while stack:
        item = stack.pop()
        if isinstance(item, Pool):
            stack.extend(item.maps)
        elif item.name and normalize_name(item.name) == needle:
            if item.state in (MapState.PICKABLE, MapState.PROTECTED):
                return item
    return None
