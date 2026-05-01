"""BeatmapCache: persistent disk-backed cache for beatmap metadata.

Loaded from disk on construction, saved back whenever new entries are fetched.
Cache file: ~/.cache/autoref/beatmaps.json (one JSON object, beatmap_id → info).
"""
import asyncio
import json
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_CACHE_FILE = Path.home() / ".cache" / "autoref" / "beatmaps.json"
_DEFAULT_OSU_DIR = Path.home() / ".cache" / "autoref" / "osu"
_PREFETCH_CONCURRENCY = 10
_OSU_FILE_URL = "https://osu.ppy.sh/osu/{bid}"


def _extract_meta(beatmap) -> dict:
    """Pull a uniform metadata dict out of an aiosu Beatmap object."""
    bset = getattr(beatmap, "beatmapset", None)
    return {
        "id":             getattr(beatmap, "id", None),
        "beatmapset_id":  getattr(beatmap, "beatmapset_id", None),
        "total_length":   getattr(beatmap, "total_length", 0),
        "title":          getattr(bset, "title", "")  if bset else "",
        "artist":         getattr(bset, "artist", "") if bset else "",
        "version":        getattr(beatmap, "version", ""),
        "stars":          round(getattr(beatmap, "difficulty_rating", 0.0) or 0.0, 2),
        "ar":             round(getattr(beatmap, "ar", 0.0) or 0.0, 1),
        "od":             round(getattr(beatmap, "accuracy", 0.0) or 0.0, 1),
        "cs":             round(getattr(beatmap, "cs", 0.0) or 0.0, 1),
        "hp":             round(getattr(beatmap, "drain", 0.0) or 0.0, 1),
        "cached_at":      int(time.time()),
    }


class BeatmapCache:
    """Async-safe in-memory dict backed by a JSON file.

    Single source of truth for beatmap metadata. Metadata schema is the union
    of fields needed by the lobby (total_length) and the web UI (stars, ar,
    od, cs, hp, beatmapset_id, etc).
    """

    def __init__(self, cache_file: Path = _DEFAULT_CACHE_FILE,
                 osu_dir: Path = _DEFAULT_OSU_DIR):
        self._path = Path(cache_file)
        self._osu_dir = Path(osu_dir)
        self._data: dict[int, dict] = {}
        self._lock = asyncio.Lock()
        self._osu_locks: dict[int, asyncio.Lock] = {}
        self._failed_osu: set[int] = set()
        self._load()

    # ---------------------------------------------------------------- disk I/O

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text())
            self._data = {int(k): v for k, v in raw.items()}
            logger.debug("beatmap cache: loaded %d entries from %s", len(self._data), self._path)
        except Exception as exc:
            logger.warning("beatmap cache: failed to load %s: %s", self._path, exc)

    def _save(self) -> None:
        """Atomic write: dump to a temp file, fsync, then os.replace()."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(self._path.suffix + ".tmp")
            payload = json.dumps({str(k): v for k, v in self._data.items()}, indent=2)
            with open(tmp, "w") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self._path)
        except Exception as exc:
            logger.warning("beatmap cache: failed to save: %s", exc)

    # ---------------------------------------------------------------- public

    def get(self, beatmap_id: int) -> dict | None:
        return self._data.get(int(beatmap_id))

    async def fetch_one(self, beatmap_id: int, client=None,
                        force: bool = False) -> dict | None:
        """Return cached metadata for `beatmap_id`, fetching once on miss.

        Set `force=True` to bypass the cache and re-fetch from the API.
        """
        bid = int(beatmap_id)
        if not force:
            cached = self._data.get(bid)
            if cached is not None:
                return cached

        if client is not None:
            try:
                beatmap = await client.get_beatmap(bid)
            except Exception as exc:
                logger.warning("beatmap cache: failed to fetch %d: %s", bid, exc)
                return None
        else:
            from ..client import make_client
            async with make_client() as c:
                try:
                    beatmap = await c.get_beatmap(bid)
                except Exception as exc:
                    logger.warning("beatmap cache: failed to fetch %d: %s", bid, exc)
                    return None

        meta = _extract_meta(beatmap)
        async with self._lock:
            self._data[bid] = meta
            self._save()
        return meta

    async def refresh(self, beatmap_id: int, client=None) -> dict | None:
        """Re-fetch a single beatmap, overwriting any cached entry."""
        return await self.fetch_one(beatmap_id, client=client, force=True)

    def is_stale(self, beatmap_id: int, max_age_s: int) -> bool:
        """True if entry missing or `cached_at` older than `max_age_s` seconds."""
        entry = self._data.get(int(beatmap_id))
        if entry is None:
            return True
        cached_at = entry.get("cached_at")
        if not isinstance(cached_at, (int, float)):
            return True
        return (time.time() - cached_at) > max_age_s

    # ----------------------------------------------------------- .osu files

    def osu_path(self, beatmap_id: int) -> Path:
        """Return the on-disk path for a beatmap's `.osu` file (may not exist)."""
        return self._osu_dir / f"{int(beatmap_id)}.osu"

    def is_osu_unavailable(self, beatmap_id: int) -> bool:
        """True if a previous fetch for this bid failed within the current process."""
        return int(beatmap_id) in self._failed_osu

    def mark_osu_unavailable(self, beatmap_id: int) -> None:
        """Mark a beatmap's `.osu` as unfetchable so future calls short-circuit."""
        self._failed_osu.add(int(beatmap_id))

    def clear_osu_unavailable(self, beatmap_id: int | None = None) -> None:
        """Clear the in-process unfetchable flag. Pass None to clear all."""
        if beatmap_id is None:
            self._failed_osu.clear()
        else:
            self._failed_osu.discard(int(beatmap_id))

    async def get_osu_path(self, beatmap_id: int) -> Path | None:
        """Return path to the cached `.osu` file, downloading once on miss.

        Returns None on download failure. Subsequent calls for the same bid
        within the same process short-circuit via the in-memory negative
        cache so a single bad map doesn't trigger N network calls per stats
        recompute. Restart the process (or call `clear_osu_unavailable()`)
        to retry.
        """
        bid = int(beatmap_id)
        if bid in self._failed_osu:
            return None
        path = self.osu_path(bid)
        if path.exists() and path.stat().st_size > 0:
            return path

        lock = self._osu_locks.setdefault(bid, asyncio.Lock())
        async with lock:
            if bid in self._failed_osu:
                return None
            if path.exists() and path.stat().st_size > 0:
                return path
            try:
                import aiohttp
            except ImportError:
                logger.error("beatmap cache: aiohttp not installed; cannot fetch .osu")
                self._failed_osu.add(bid)
                return None
            url = _OSU_FILE_URL.format(bid=bid)
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            logger.warning("beatmap cache: %s returned HTTP %d", url, resp.status)
                            self._failed_osu.add(bid)
                            return None
                        body = await resp.read()
            except Exception as exc:
                logger.warning("beatmap cache: failed to download %s: %s", url, exc)
                self._failed_osu.add(bid)
                return None

            if not body:
                logger.warning("beatmap cache: empty .osu body for %d (marked unavailable)", bid)
                self._failed_osu.add(bid)
                return None

            try:
                self._osu_dir.mkdir(parents=True, exist_ok=True)
                tmp = path.with_suffix(path.suffix + ".tmp")
                tmp.write_bytes(body)
                os.replace(tmp, path)
            except Exception as exc:
                logger.warning("beatmap cache: failed to write %s: %s", path, exc)
                self._failed_osu.add(bid)
                return None
            return path

    async def prefetch(self, beatmap_ids: list[int], client=None) -> None:
        """Fetch metadata for any IDs not already cached. Safe to call concurrently.

        Pass `client` (an aiosu.v2.Client) to reuse an existing API session.
        If omitted, a fresh client is created via autoref.client.make_client().
        """
        missing = [int(bid) for bid in beatmap_ids if int(bid) not in self._data]
        if not missing:
            return

        sem = asyncio.Semaphore(_PREFETCH_CONCURRENCY)

        async def _one(c, bid):
            async with sem:
                return await c.get_beatmap(bid)

        if client is not None:
            results = await asyncio.gather(
                *(_one(client, bid) for bid in missing),
                return_exceptions=True,
            )
        else:
            from ..client import make_client
            async with make_client() as c:
                results = await asyncio.gather(
                    *(_one(c, bid) for bid in missing),
                    return_exceptions=True,
                )

        async with self._lock:
            fetched = 0
            for bid, result in zip(missing, results):
                if isinstance(result, Exception):
                    logger.warning("beatmap cache: failed to fetch %d: %s", bid, result)
                    continue
                self._data[bid] = _extract_meta(result)
                fetched += 1
            if fetched:
                self._save()
                logger.info("beatmap cache: fetched %d new entries", fetched)


# ----------------------------------------------------------------------------
# Process-wide singleton: bot + web server share one BeatmapCache instance so
# they coordinate through the same in-memory dict + asyncio.Lock instead of
# racing each other through the JSON file on disk.
# ----------------------------------------------------------------------------

_SHARED: BeatmapCache | None = None


def get_beatmap_cache() -> BeatmapCache:
    global _SHARED
    if _SHARED is None:
        _SHARED = BeatmapCache()
    return _SHARED
