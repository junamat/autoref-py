"""PlayRunner: drives a single map through ready/start/result + score enrichment."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from ..enums import Step
from ..utils import find_map as _find_map, normalize_name as _normalize

if TYPE_CHECKING:
    from .base import AutoRef

logger = logging.getLogger(__name__)


class PlayRunner:
    def __init__(self, ref: "AutoRef"):
        self.ref = ref

    async def play_map(self, beatmap_id: int, team_index: int, step: Step):
        """Set the map, wait for ready, start, wait for result, record it."""
        ref = self.ref
        pm = _find_map(ref.match, beatmap_id)
        gamemode = ref.match.ruleset.gamemode.value
        mods = pm.effective_mods() if pm else None

        await ref.lobby.set_map(beatmap_id, gamemode)
        enforced = ref.match.ruleset.enforced_mods
        extra = str(mods) if mods else ""
        base_mods = str(enforced) if enforced else ""
        combined = extra if "Freemod" in extra else (extra + base_mods)
        if combined:
            await ref.lobby.set_mods(combined)

        ref._map_in_progress = True
        try:
            while True:
                ref._abort_event.clear()

                if ref._close_event.is_set():
                    return None

                await asyncio.sleep(ref.timers.between_maps)

                await ref.lobby.timer(ref.timers.ready_up)
                ready_t = asyncio.create_task(ref.lobby.wait_for_all_ready())
                timer_t = asyncio.create_task(ref.lobby.wait_for_timer())
                abort_t = asyncio.create_task(ref._abort_event.wait())
                done, pending = await asyncio.wait(
                    {ready_t, timer_t, abort_t}, return_when=asyncio.FIRST_COMPLETED
                )
                for t in pending:
                    t.cancel()
                await asyncio.gather(*pending, return_exceptions=True)

                if abort_t in done:
                    if ref._close_event.is_set():
                        return None
                    await ref.lobby.say("Map aborted. Waiting for everyone to ready up again.")
                    continue

                await ref.lobby.start(delay=ref.timers.start_map)

                result_t = asyncio.create_task(ref.lobby.wait_for_match_end())
                abort_t2 = asyncio.create_task(ref._abort_event.wait())
                done2, pending2 = await asyncio.wait(
                    {result_t, abort_t2}, return_when=asyncio.FIRST_COMPLETED
                )
                for t in pending2:
                    t.cancel()
                await asyncio.gather(*pending2, return_exceptions=True)

                if abort_t2 in done2:
                    if ref._close_event.is_set():
                        return None
                    await ref.lobby.say("Map aborted. Waiting for everyone to ready up again.")
                    continue

                result = result_t.result()
                break
        finally:
            ref._map_in_progress = False

        ref.match.record_action(team_index, step, beatmap_id)
        turn = len(ref.match.match_status) - 1
        self.spawn_score_fetch(turn, beatmap_id)
        return result

    def spawn_score_fetch(self, turn: int, beatmap_id: int) -> None:
        """Fire-and-forget API enrichment for the just-finished game."""
        ref = self.ref
        if ref.score_fetcher is None:
            return
        lobby_id = ref.lobby.room_id
        if lobby_id is None:
            return
        task = asyncio.create_task(self.do_score_fetch(turn, beatmap_id, lobby_id))
        ref._score_fetch_tasks.append(task)
        task.add_done_callback(lambda t: ref._score_fetch_tasks.remove(t)
                               if t in ref._score_fetch_tasks else None)

    async def do_score_fetch(self, turn: int, beatmap_id: int, lobby_id: int) -> None:
        ref = self.ref
        fetcher = ref.score_fetcher
        if fetcher is None:
            return
        try:
            scores = await fetcher.fetch_for_game(lobby_id, beatmap_id)
        except Exception:
            logger.exception("score fetch failed for turn=%d map=%d", turn, beatmap_id)
            return
        if not scores:
            return
        # Annotate user_id -> team_index via roster .id; fall back to normalized username.
        id_to_team: dict[int, tuple[str, int]] = {}
        name_to_team: dict[str, tuple[str, int]] = {}
        for ti, team in enumerate(ref.match.teams):
            for p in team.players:
                pid = getattr(p, "id", None)
                pname = getattr(p, "username", None) or ""
                if pid is not None:
                    id_to_team[int(pid)] = (pname, ti)
                if pname:
                    name_to_team[_normalize(pname)] = (pname, ti)
        unmatched = []
        for s in scores:
            username, team_index = id_to_team.get(int(s["user_id"]), (None, None))
            if team_index is None and s.get("api_username"):
                username, team_index = name_to_team.get(
                    _normalize(s["api_username"]), (None, None)
                )
            s["username"] = username or s.get("api_username")
            s["team_index"] = team_index
            if team_index is None:
                unmatched.append((s["user_id"], s.get("api_username")))
        if unmatched:
            logger.warning("score fetch: unmatched players for turn=%d map=%d: %s",
                           turn, beatmap_id, unmatched)
        logger.info("score fetch: turn=%d map=%d enriched %d scores",
                    turn, beatmap_id, len(scores))
        ref.match.add_game_scores(turn, beatmap_id, scores)
