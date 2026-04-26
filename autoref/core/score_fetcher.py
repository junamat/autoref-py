"""ScoreFetcher: fetches API-rich per-player scores for a finished MP game.

IRC `playerFinished` only reports username/score/passed. The API exposes mods,
accuracy, max_combo and rank — needed for stats. The osu! match endpoint takes
a few seconds to index a game after it ends, so we poll with backoff.
"""
import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _score_to_dict(s: Any) -> dict:
    mods: list[str] = []
    if s.mods:
        for m in s.mods:
            mods.append(m.acronym if hasattr(m, "acronym") else str(m))
    return {
        "user_id":   int(s.user_id),
        "score":     int(s.score),
        "accuracy":  float(s.accuracy),
        "max_combo": int(s.max_combo),
        "passed":    bool(s.passed),
        "perfect":   bool(getattr(s, "perfect", False)),
        "mods":      mods,
        "rank":      s.rank.value if getattr(s, "rank", None) else None,
    }


class ScoreFetcher:
    """Polls the osu! match endpoint until a game with the given beatmap_id is found.

    A new instance can be shared across maps in a single match. Tracks the highest
    seen game id to avoid returning a stale earlier occurrence of the same beatmap_id.
    """

    def __init__(
        self,
        client: Any,  # aiosu.v2.Client — kept generic for testability
        *,
        timeout: float = 90.0,
        initial_delay: float = 5.0,
        max_delay: float = 30.0,
    ):
        self._client = client
        self._timeout = timeout
        self._initial_delay = initial_delay
        self._max_delay = max_delay
        self._last_game_id: int = 0  # highest game.id observed across calls

    async def fetch_for_game(
        self, lobby_id: int, beatmap_id: int
    ) -> list[dict] | None:
        """Return enriched scores for the most recent game on `beatmap_id` after
        `_last_game_id`. None on timeout or unrecoverable error."""
        loop = asyncio.get_event_loop()
        deadline = loop.time() + self._timeout
        delay = self._initial_delay

        while loop.time() < deadline:
            await asyncio.sleep(delay)
            try:
                resp = await self._client.get_multiplayer_match(lobby_id)
            except Exception:
                logger.exception("get_multiplayer_match failed")
                delay = min(delay * 2, self._max_delay)
                continue

            for ev in reversed(resp.events):
                game = getattr(ev, "game", None)
                if (game is None
                        or game.beatmap_id != beatmap_id
                        or game.end_time is None
                        or not game.scores
                        or int(game.id) <= self._last_game_id):
                    continue
                self._last_game_id = int(game.id)
                return [_score_to_dict(s) for s in game.scores]

            delay = min(delay * 2, self._max_delay)

        logger.warning(
            "ScoreFetcher: timed out waiting for game on map %d in lobby %d",
            beatmap_id, lobby_id,
        )
        return None
