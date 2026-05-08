"""VotedQualifiersAutoRef: map voting per turn, optional player quit, consumable pool."""
from __future__ import annotations

import asyncio
import os
import random

import bancho

from ..core.beatmap_cache import BeatmapCache, get_beatmap_cache
from ..core.commands import Command
from ..core.enums import MapState, Step
from ..core.models import Match, PlayableMap, Timers
from ..core.ref import AutoRef
from ..core.utils import find_map as _find_map
from ..core.utils import normalize_name as _normalize

_FORTUNES = [
    "the dice favor {map} today.",
    "{player}'s luck is running thin.",
    "all signs point to a random roll.",
    "the wheel whispers your name.",
    "trust the seed.",
    "destiny's bracket is cruel.",
    "rolling a nat 1 — sorry, wrong game.",
    "the rng gods demand a sacrifice.",
    "every pass echoes in eternity.",
    "the next pick will be glorious. probably.",
    "consult the seed before despairing.",
    "i predict... a map. yes.",
    "{player}, your picks have been noted by the rng.",
    "the void picks. the void chooses. the void rolls.",
]


class VotedQualifiersAutoRef(AutoRef):
    """Qualifiers where players vote on maps each turn. Supports multiple runs and optional quit."""

    def __init__(
        self,
        client: bancho.BanchoClient,
        match: Match,
        room_name: str,
        runs: int = 1,
        vote_timeout: int = 90,
        empty_grace: int = 300,
        timers: Timers | None = None,
        beatmap_cache: BeatmapCache | None = None,
        seed: int | None = None,
        **kwargs,
    ):
        super().__init__(client, match, room_name, timers, **kwargs)
        self.runs = runs
        self._maps: list[PlayableMap] = match.pool.flatten()
        self._play_counts: dict[int, int] = {m.beatmap_id: 0 for m in self._maps}
        self._run_index: int = 0
        self._maps_in_run: int = 0
        self._active_players: set[str] = set()
        self._quit_players: set[str] = set()
        self._beatmap_cache: BeatmapCache = beatmap_cache or get_beatmap_cache()
        self._seed: int = seed if seed is not None else int.from_bytes(os.urandom(8), "big")
        self._rng: random.Random = random.Random(self._seed)
        self._vote_timeout: int = vote_timeout
        self._current_picker: str | None = None
        self._lobby_repopulated: asyncio.Event = asyncio.Event()
        self._empty_grace: int = empty_grace
        self._grace_deadline: float | None = None
        self._grace_task: asyncio.Task | None = None
        self._last_pick_source: dict = {}
        self._vote_log: list[dict] = []

    # -------------------------------------------------------------- availability

    def _available_maps(self) -> list[PlayableMap]:
        remaining = [m for m in self._maps if self._play_counts[m.beatmap_id] < self.runs]
        if not remaining:
            return []
        floor = min(self._play_counts[m.beatmap_id] for m in remaining)
        return [m for m in remaining if self._play_counts[m.beatmap_id] == floor]

    def _find_in_available(self, text: str, available: list[PlayableMap]) -> PlayableMap | None:
        needle = _normalize(text)
        for pm in available:
            if pm.name and _normalize(pm.name) == needle:
                return pm
        return None

    def _effective_pickers(self) -> list[str]:
        in_lobby = {_normalize(p) for p in self.lobby.players}
        return sorted(self._active_players & in_lobby)

    def _map_name(self, beatmap_id: int) -> str:
        for m in self._maps:
            if m.beatmap_id == beatmap_id:
                return m.name or str(beatmap_id)
        return str(beatmap_id)

    # -------------------------------------------------------------- next_step

    def next_step(self, match_status) -> tuple[int, Step]:
        if not self._active_players:
            return (0, Step.FINISH)
        total_target = self.runs * len(self._maps)
        total_played = sum(self._play_counts.values())
        if total_played >= total_target:
            return (0, Step.FINISH)
        return (0, Step.PICK)

    # -------------------------------------------------------------- pre_loop

    async def _pre_loop(self) -> None:
        ids = [m.beatmap_id for m in self._maps]
        await self._beatmap_cache.prefetch(ids)
        self._play_counts = {m.beatmap_id: 0 for m in self._maps}
        for team in self.match.teams:
            for player in team.players:
                self._active_players.add(_normalize(player.username))
        self.lobby.add_presence_hook(self._on_presence)

    # -------------------------------------------------------------- announce (overrides)

    async def _pre_pick(self, team_index: int) -> None:
        pass

    async def announce_next_pick(self, team_index: int) -> None:
        pass

    # -------------------------------------------------------------- pick flow

    async def await_pick(self, team_index: int) -> int | None:
        available = self._available_maps()
        if not available:
            return None

        while True:
            effective = self._effective_pickers()
            if effective:
                break
            if not self._active_players:
                return None
            await self.lobby.say("Waiting for players to return…")
            self._lobby_repopulated.clear()
            close_task = asyncio.ensure_future(self._close_event.wait())
            repop_task = asyncio.ensure_future(self._lobby_repopulated.wait())
            await asyncio.wait(
                {repop_task, close_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            close_task.cancel()
            repop_task.cancel()
            if self._close_event.is_set():
                return None

        passers: list[str] = []

        # single effective picker — commit immediately on valid input, no pass
        if len(effective) == 1:
            picker = effective[0]
            result, via = await self._collect_pick(picker, available, allow_pass=False, commit_on_pick=True)
            if result is None:
                return None
            if result in ("__absent__", "__empty__"):
                await self._wait_for_repopulate_or_close()
                if self._close_event.is_set():
                    return None
                return await self.await_pick(team_index)
            assert isinstance(result, int)
            self._vote_log.append({
                "picker": picker,
                "map": self._map_name(result),
                "via": via or "chosen",
                "passers": [],
            })
            return result

        # multi-picker rotation with pass-drops
        candidates = list(effective)
        self._rng.shuffle(candidates)
        for picker in candidates:
            if picker not in self._effective_pickers():
                continue
            await self.lobby.say(
                f"{picker} picks the next map. Type a map code, 'random', or 'pass'. "
                f"You have {self._vote_timeout}s."
            )
            result, via = await self._collect_pick(picker, available, allow_pass=True)
            if result == "__pass__":
                passers.append(picker)
                continue
            if result == "__absent__":
                continue
            if result == "__empty__":
                await self._wait_for_repopulate_or_close()
                if self._close_event.is_set():
                    return None
                return await self.await_pick(team_index)
            if result is None:
                return None
            assert isinstance(result, int)
            self._vote_log.append({
                "picker": picker,
                "map": self._map_name(result),
                "via": via or "chosen",
                "passers": passers[:],
            })
            return result

        # every candidate passed or was void → random
        await self.lobby.say("No one picked — rolling a random map.")
        beatmap_id = self._rng.choice(available).beatmap_id
        self._vote_log.append({
            "picker": None,
            "map": self._map_name(beatmap_id),
            "via": "all-passed-random",
            "passers": passers[:],
        })
        return beatmap_id

    async def _collect_pick(
        self,
        picker_username: str,
        available: list[PlayableMap],
        allow_pass: bool,
        commit_on_pick: bool = False,
    ) -> tuple[int | str | None, str | None]:
        """Wait under bancho timer for picker's chat message.
        Returns (beatmap_id | signal, via_str). via_str is 'chosen', 'random', 'timer-random', or None.
        commit_on_pick: commit immediately on valid input instead of holding until timer close."""
        self._current_picker = picker_username
        tentative: int | None = None
        tentative_via: str | None = None

        loop = asyncio.get_event_loop()
        pass_future: asyncio.Future = loop.create_future()
        pick_future: asyncio.Future = loop.create_future()
        self._step_cancel_future = loop.create_future()

        def on_message(msg) -> None:
            nonlocal tentative, tentative_via
            if _normalize(getattr(msg.user, "username", "")) != picker_username:
                return
            text = msg.message.strip()
            if allow_pass and text.lower() == "pass":
                if not pass_future.done():
                    pass_future.set_result("__pass__")
                return
            if text.lower() in ("random", "rand", "r"):
                tentative = self._rng.choice(available).beatmap_id
                tentative_via = "random"
                if commit_on_pick and not pick_future.done():
                    pick_future.set_result(tentative)
                else:
                    asyncio.ensure_future(self.lobby.say("Tentative: random"))
                return
            pm = self._find_in_available(text, available)
            if pm is not None:
                tentative = pm.beatmap_id
                tentative_via = "chosen"
                if commit_on_pick and not pick_future.done():
                    pick_future.set_result(pm.beatmap_id)
                else:
                    asyncio.ensure_future(self.lobby.say(f"Tentative: {pm.name or pm.beatmap_id}"))
                return
            # Map exists in pool but not available this turn
            pm_all = next(
                (m for m in self._maps if m.name and _normalize(m.name) == _normalize(text)),
                None,
            )
            if pm_all:
                asyncio.ensure_future(self.lobby.say(f"{text} is unavailable this turn."))
            else:
                asyncio.ensure_future(self.lobby.say(f"Unknown or unavailable map: {text}"))

        await self.lobby.timer(self._vote_timeout)
        self.lobby.channel.on("message", on_message)
        try:
            timer_task = asyncio.ensure_future(self.lobby.wait_for_timer())
            close_task = asyncio.ensure_future(self._close_event.wait())
            wait_set = {pass_future, pick_future, timer_task, close_task, self._step_cancel_future}

            done, pending = await asyncio.wait(wait_set, return_when=asyncio.FIRST_COMPLETED)
            for f in pending:
                f.cancel()

            if self._close_event.is_set() or self._step_cancel_future in done:
                return (None, None)

            if pass_future in done:
                await self.lobby.abort_timer()
                return ("__pass__", None)

            # Immediate commit (single-player path)
            if pick_future in done and not pick_future.cancelled():
                await self.lobby.abort_timer()
                return (pick_future.result(), tentative_via)

            # Timer expired — validate presence
            picker_present = picker_username in self._effective_pickers()
            if tentative is not None:
                if picker_present:
                    return (tentative, tentative_via)
                return ("__absent__", None)
            if self._effective_pickers():
                beatmap_id = self._rng.choice(available).beatmap_id
                return (beatmap_id, "timer-random")
            return ("__empty__", None)
        finally:
            self._current_picker = None
            self._step_cancel_future = None
            self.lobby.channel.remove_listener("message", on_message)

    async def _wait_for_repopulate_or_close(self) -> None:
        self._ensure_grace_running()
        while not self._effective_pickers() and not self._close_event.is_set():
            self._lobby_repopulated.clear()
            await self.lobby.timer(self._vote_timeout)
            repop_task = asyncio.ensure_future(self._lobby_repopulated.wait())
            close_task = asyncio.ensure_future(self._close_event.wait())
            timer_task = asyncio.ensure_future(self.lobby.wait_for_timer())
            await asyncio.wait(
                {repop_task, close_task, timer_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            repop_task.cancel()
            close_task.cancel()
            timer_task.cancel()

    # -------------------------------------------------------------- handle_pick

    async def handle_pick(self, team_index: int, beatmap_id: int) -> None:
        pm = _find_map(self.match, beatmap_id)
        name = pm.name if pm and pm.name else str(beatmap_id)
        await self.lobby.say(f"Playing: {name}")
        await self.play_map(beatmap_id, team_index, Step.PICK)
        self._play_counts[beatmap_id] += 1
        self._maps_in_run += 1
        if self._maps_in_run >= len(self._maps):
            self._maps_in_run = 0
            self._run_index += 1
        if pm and self._play_counts[beatmap_id] >= self.runs:
            pm.state = MapState.PLAYED

    # -------------------------------------------------------------- presence / grace

    async def _on_presence(self) -> None:
        if self._effective_pickers():
            self._cancel_grace()
            self._lobby_repopulated.set()
        elif self._active_players:
            self._ensure_grace_running()

    def _ensure_grace_running(self) -> None:
        if self._effective_pickers():
            return
        if self._grace_task and not self._grace_task.done():
            return
        loop = asyncio.get_event_loop()
        self._grace_deadline = loop.time() + self._empty_grace
        self._grace_task = asyncio.create_task(self._grace_close_when_expired())

    async def _grace_close_when_expired(self) -> None:
        assert self._grace_deadline is not None
        remaining = self._grace_deadline - asyncio.get_event_loop().time()
        try:
            await asyncio.sleep(max(0.0, remaining))
        except asyncio.CancelledError:
            return
        if not self._effective_pickers():
            await self.lobby.say(f"Lobby empty for {self._empty_grace}s — closing.")
            self._close_event.set()

    def _cancel_grace(self) -> None:
        if self._grace_task and not self._grace_task.done():
            self._grace_task.cancel()
        self._grace_task = None
        self._grace_deadline = None

    # -------------------------------------------------------------- announce_finish

    async def announce_finish(self, team_index: int) -> None:
        total = sum(self._play_counts.values())
        await self.lobby.say(f"Match complete — {total} maps played.")
        if self._quit_players:
            await self.lobby.say(f"Players quit: {', '.join(sorted(self._quit_players))}")

    # -------------------------------------------------------------- persistence

    def to_state_dict(self) -> dict:
        d = super().to_state_dict()
        d.update({
            "play_counts": self._play_counts,
            "run_index": self._run_index,
            "maps_in_run": self._maps_in_run,
            "active_players": sorted(self._active_players),
            "quit_players": sorted(self._quit_players),
            "seed": self._seed,
            "vote_log": list(self._vote_log),
            "current_picker": self._current_picker,
        })
        return d

    def from_state_dict(self, d: dict) -> None:
        super().from_state_dict(d)
        self._play_counts = {int(k): v for k, v in d.get("play_counts", {}).items()}
        self._run_index = d.get("run_index", 0)
        self._maps_in_run = d.get("maps_in_run", 0)
        self._active_players = set(d.get("active_players", []))
        self._quit_players = set(d.get("quit_players", []))
        self._seed = d.get("seed", self._seed)
        self._rng = random.Random(self._seed)
        self._vote_log = list(d.get("vote_log", []))
        self._current_picker = d.get("current_picker")

    # -------------------------------------------------------------- state

    def _get_state(self) -> dict:
        state = super()._get_state()
        loop = asyncio.get_event_loop()
        grace_remaining = (
            max(0.0, self._grace_deadline - loop.time())
            if self._grace_deadline is not None
            else None
        )
        maps_list = []
        for pm in self._maps:
            count = self._play_counts.get(pm.beatmap_id, 0)
            if count >= self.runs:
                map_state = "played"
            elif count > 0:
                map_state = "partial"
            else:
                map_state = "upcoming"
            meta = self._beatmap_cache.get(pm.beatmap_id)
            maps_list.append({
                "code": pm.name or str(pm.beatmap_id),
                "state": map_state,
                "play_count": count,
                "tb": False,
                "length": meta["total_length"] if meta else None,
                "title": meta["title"] if meta else None,
                "artist": meta["artist"] if meta else None,
            })
        state["voted"] = True
        state["active_players"] = sorted(self._active_players)
        state["quit_players"] = sorted(self._quit_players)
        state["current_picker"] = self._current_picker
        state["seed"] = self._seed
        state["vote_log"] = list(self._vote_log)
        state["grace_remaining"] = grace_remaining
        state["maps"] = maps_list
        return state

    # -------------------------------------------------------------- commands

    def _commands(self) -> list[Command]:
        return super()._commands() + [
            Command("quit",      [],         "leave the match (final, stats saved)", section="voted", scope="anyone"),
            Command("seed",      [],         "show the rng seed used for this match", section="voted", scope="anyone"),
            Command("luck",      [],         "show per-player random/pass/pick counts", section="voted", scope="anyone"),
            Command("history",   ["hist"],   "show vote outcomes log", section="voted", scope="anyone"),
            Command("reseed",    [],         "reseed rng (ref only) — discloses old + new seed", section="voted", scope="ref"),
            Command("blame",     [],         "who has passed the most", section="voted", scope="anyone"),
            Command("fortune",   ["fort"],   "rng-flavored one-liner", section="voted", scope="anyone"),
            Command("consensus", ["tide"],   "who picks with the crowd vs alone", section="voted", scope="anyone"),
        ]

    async def _dispatch_command(self, cmd: str, args: list[str], source: str) -> bool:
        match cmd:
            case "quit":
                await self._handle_quit(source)
            case "seed":
                await self._handle_seed(source)
            case "luck":
                await self._handle_luck(source)
            case "history" | "hist":
                await self._handle_history(source)
            case "reseed":
                await self._handle_reseed(source, args)
            case "blame":
                await self._handle_blame(source)
            case "fortune" | "fort":
                await self._handle_fortune(source)
            case "consensus" | "tide":
                await self._handle_consensus(source)
            case _:
                return await super()._dispatch_command(cmd, args, source)
        return True

    # -------------------------------------------------------------- command handlers

    async def _handle_quit(self, source: str) -> None:
        user = _normalize(source)
        if source in self._trusted_sources():
            await self.lobby.reply("'quit' is a player-only command (must come from chat).", source)
            return
        if user not in self._active_players:
            return
        self._active_players.discard(user)
        self._quit_players.add(user)
        await self.lobby.say(f"{source} quit. Stats saved.")
        self._save_match()
        if self._current_picker == user:
            self._cancel_step()

    async def _handle_seed(self, source: str) -> None:
        await self.lobby.say(f"rng seed: {self._seed}")

    async def _handle_reseed(self, source: str, args: list[str]) -> None:
        old = self._seed
        if args:
            try:
                new = int(args[0])
            except ValueError:
                await self.lobby.say(f"Usage: {self.ref_prefix}reseed [int]")
                return
        else:
            new = int.from_bytes(os.urandom(8), "big")
        self._seed = new
        self._rng = random.Random(new)
        await self.lobby.say(f"rng reseeded. old={old} new={new}")

    async def _handle_history(self, source: str) -> None:
        if not self._vote_log:
            await self.lobby.say("No votes yet.")
            return
        for i, e in enumerate(self._vote_log, 1):
            passers = f" (passes: {', '.join(e['passers'])})" if e["passers"] else ""
            picker = e["picker"] or "—"
            await self.lobby.say(f"#{i} {e['map']} via {e['via']} by {picker}{passers}")

    async def _handle_luck(self, source: str) -> None:
        counts: dict[str, dict[str, int]] = {}
        for e in self._vote_log:
            if e["picker"]:
                d = counts.setdefault(e["picker"], {"chosen": 0, "random": 0, "passed": 0})
                d["chosen" if e["via"] == "chosen" else "random"] += 1
            for p in e["passers"]:
                counts.setdefault(p, {"chosen": 0, "random": 0, "passed": 0})["passed"] += 1
        if not counts:
            await self.lobby.say("No data.")
            return
        rows = sorted(counts.items(), key=lambda kv: -kv[1]["chosen"])
        for name, d in rows:
            await self.lobby.say(f"{name}: chosen={d['chosen']} random={d['random']} passed={d['passed']}")

    async def _handle_blame(self, source: str) -> None:
        counts: dict[str, int] = {}
        for e in self._vote_log:
            for p in e["passers"]:
                counts[p] = counts.get(p, 0) + 1
        if not counts:
            await self.lobby.say("Nobody to blame yet.")
            return
        top = max(counts.values())
        leaders = [n for n, c in counts.items() if c == top]
        await self.lobby.say(f"Most passes ({top}): {', '.join(leaders)}")

    async def _handle_fortune(self, source: str) -> None:
        line = self._rng.choice(_FORTUNES)
        avail = self._available_maps()
        pickers = self._effective_pickers()
        fmap = self._rng.choice(avail).name if avail else "the pool"
        fplayer = self._rng.choice(pickers) if pickers else "someone"
        await self.lobby.say(line.format(map=fmap, player=fplayer))

    async def _handle_consensus(self, source: str) -> None:
        map_to_pickers: dict[str, set[str]] = {}
        player_picks: dict[str, list[str]] = {}
        for e in self._vote_log:
            if not e["picker"] or e["via"] not in ("chosen", "random"):
                continue
            m = e["map"]
            map_to_pickers.setdefault(m, set()).add(e["picker"])
            player_picks.setdefault(e["picker"], []).append(m)
        if not player_picks:
            await self.lobby.say("No picks yet.")
            return
        alignment: dict[str, int] = {}
        for p, picks in player_picks.items():
            alignment[p] = sum(len(map_to_pickers[m]) - 1 for m in picks)
        top_map = max(map_to_pickers.items(), key=lambda kv: len(kv[1]))
        await self.lobby.say(f"most-picked: {top_map[0]} ({len(top_map[1])} pickers)")
        ranked = sorted(alignment.items(), key=lambda kv: -kv[1])
        await self.lobby.say("crowd-alignment: " + ", ".join(f"{p}={s}" for p, s in ranked))
        if ranked:
            lone = ranked[-1]
            await self.lobby.say(f"lone wolf: {lone[0]} (alignment={lone[1]})")
