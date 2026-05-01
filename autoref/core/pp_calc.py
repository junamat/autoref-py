"""Local pp calculator powered by rosu-pp-py.

Optional component. If `rosu-pp-py` isn't installed, every entry point returns
None and logs a one-time warning so callers can degrade gracefully.

Public API:
    await compute_pp(beatmap_id, mods, accuracy, max_combo, misses=0, mode=0)
"""
from __future__ import annotations

import logging
from typing import Iterable

from .beatmap_cache import BeatmapCache, get_beatmap_cache

logger = logging.getLogger(__name__)

_warned_missing = False


def _rosu():
    """Lazy-import rosu_pp_py. Returns module or None."""
    global _warned_missing
    try:
        import rosu_pp_py as r
        return r
    except ImportError:
        if not _warned_missing:
            logger.warning("rosu-pp-py not installed; pp calc disabled. "
                           "Install with: pip install -e '.[pp]'")
            _warned_missing = True
        return None


# osu! mod string → rosu_pp_py mod acronym (rosu wants 2-letter uppercase strs)
# rosu accepts a list of acronym strings. Pass-through mostly works.
def _normalize_mods(mods: Iterable[str] | str | int | None) -> list[str]:
    if mods is None:
        return []
    if isinstance(mods, int):
        # Bitfield → not handled here; caller should pass a list[str].
        return []
    if isinstance(mods, str):
        # "HDDT" → ["HD", "DT"]
        s = mods.upper()
        return [s[i:i+2] for i in range(0, len(s), 2)]
    out: list[str] = []
    for m in mods:
        if not m:
            continue
        s = str(m).upper()
        if len(s) == 2:
            out.append(s)
    return out


async def compute_pp(
    beatmap_id: int,
    mods: Iterable[str] | str | None = None,
    accuracy: float = 100.0,
    max_combo: int | None = None,
    misses: int = 0,
    mode: int = 0,
    cache: BeatmapCache | None = None,
) -> float | None:
    """Compute pp for a single play.

    Args:
        beatmap_id: osu! beatmap id.
        mods: list of 2-letter mod acronyms (e.g. ["HD", "DT"]).
        accuracy: 0-100.
        max_combo: combo achieved on the play. None → assume FC.
        misses: miss count (0 if unknown).
        mode: 0=osu!, 1=taiko, 2=catch, 3=mania.
        cache: optional shared BeatmapCache; defaults to module singleton.

    Returns:
        pp as float, or None if rosu-pp-py is missing or the .osu file
        couldn't be fetched / parsed.
    """
    r = _rosu()
    if r is None:
        return None

    cache = cache or get_beatmap_cache()
    osu_path = await cache.get_osu_path(int(beatmap_id))
    if osu_path is None:
        return None

    try:
        beatmap = r.Beatmap(path=str(osu_path))
        if mode != 0:
            beatmap.convert(r.GameMode(mode))
        kwargs: dict = {
            "mods": _normalize_mods(mods),
            "accuracy": float(accuracy),
            "misses": int(misses),
        }
        if max_combo is not None:
            kwargs["combo"] = int(max_combo)
        perf = r.Performance(**kwargs)
        result = perf.calculate(beatmap)
        return float(result.pp)
    except Exception as exc:
        logger.warning("pp_calc: failed for bid=%d mods=%s: %s",
                       beatmap_id, mods, exc)
        return None
