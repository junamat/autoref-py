"""BeatmapCache: persistent disk-backed cache for beatmap metadata.

Loaded from disk on construction, saved back whenever new entries are fetched.
Cache file: ~/.cache/autoref/beatmaps.json (one JSON object, beatmap_id → info).
"""
import asyncio
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_CACHE_FILE = Path.home() / ".cache" / "autoref" / "beatmaps.json"


class BeatmapCache:
    """Thread-safe in-memory dict backed by a JSON file.

    Info dict per entry: {total_length, title, artist, version}
    """

    def __init__(self, cache_file: Path = _DEFAULT_CACHE_FILE):
        self._path = Path(cache_file)
        self._data: dict[int, dict] = {}
        self._lock = asyncio.Lock()
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
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps({str(k): v for k, v in self._data.items()}, indent=2)
            )
        except Exception as exc:
            logger.warning("beatmap cache: failed to save: %s", exc)

    # ---------------------------------------------------------------- public

    def get(self, beatmap_id: int) -> dict | None:
        return self._data.get(int(beatmap_id))

    async def prefetch(self, beatmap_ids: list[int]) -> None:
        """Fetch metadata for any IDs not already cached. Safe to call concurrently."""
        missing = [int(bid) for bid in beatmap_ids if int(bid) not in self._data]
        if not missing:
            return

        from .client import make_client

        async with make_client() as client:
            results = await asyncio.gather(
                *(client.get_beatmap(bid) for bid in missing),
                return_exceptions=True,
            )

        async with self._lock:
            fetched = 0
            for bid, result in zip(missing, results):
                if isinstance(result, Exception):
                    logger.warning("beatmap cache: failed to fetch %d: %s", bid, result)
                    continue
                bset = getattr(result, "beatmapset", None)
                self._data[bid] = {
                    "total_length": getattr(result, "total_length", 0),
                    "title":   getattr(bset, "title", "")   if bset else "",
                    "artist":  getattr(bset, "artist", "")  if bset else "",
                    "version": getattr(result, "version", ""),
                }
                fetched += 1
            if fetched:
                self._save()
                logger.info("beatmap cache: fetched %d new entries", fetched)
