"""BracketAutoRef: default bracket-match controller.

Phase sequence:
    ROLL -> ORDER -> PROTECT -> BAN_1 -> PICK (maybe) BAN_2 -> PICK ... -> TB? -> DONE

The roll and order phases run in _pre_loop (see self._run_roll_phase / _run_order_phase).
next_step drives the rest. handle_other handles the tiebreaker.
"""
import asyncio
import logging
import re
from enum import Enum

from ..core.base import AutoRef, _normalize, _find_map
from ..core.enums import MapState, Step
from ..core.lobby import MatchResult, PlayerResult
from ..core.models import OrderScheme

logger = logging.getLogger(__name__)


class Phase(Enum):
    ROLL = 0
    ORDER = 1
    PROTECT = 2
    BAN_1 = 3
    PICK = 4
    BAN_2 = 5
    TB = 6
    DONE = 7


_ROLL_RE = re.compile(r"^(?P<user>\S.*?) rolls (?P<n>\d+) point\(s\)$")


class BracketAutoRef(AutoRef):
    """Default bracket match controller.

    Flow: captains !roll, roll winner picks an OrderScheme, then protects / bans
    / picks run in the order the scheme dictates. Tiebreaker triggers when any
    two teams are tied at wins_needed - 1.

    Teams: designed for N teams but the default next_picker only handles 2 (loser
    of last map picks). Override next_picker to support N>2.

    Resume is not supported in v1 — protect/ban cursors are in-memory only.
    """

    def __init__(self, client, match, room_name, *,
                 schemes=None, roll_timeout=120, timers=None, **kwargs):
        super().__init__(client, match, room_name, timers, **kwargs)
        self.schemes = schemes or match.ruleset.schemes or [OrderScheme("default")]
        self.roll_timeout = roll_timeout

        self.phase: Phase = Phase.ROLL
        self.ranking: list[int] | None = None
        self.scheme: OrderScheme | None = None

        self._protect_cursor = 0
        self._ban_cursor = 0
        self._pick_count = 0
        self._protect_seq: list[int] = []
        self._ban_seq: list[int] = []
        self._tb_triggered = False
        self._wins: list[int] = [0] * len(match.teams)
        self._last_map_winner: int | None = None
        self._roll_done = asyncio.Event()
        self._order_done = asyncio.Event()
        self._rolls: dict[int, int] = {}  # team_index -> roll value

        # TB maps start DISALLOWED so _find_map_by_input skips them until trigger.
        for pm in match.pool.flatten():
            if pm.is_tiebreaker:
                src = _find_map(match, pm.beatmap_id)
                if src is not None:
                    src.state = MapState.DISALLOWED

    # ---------------------------------------------------------- commit scheme

    def commit_scheme(self, scheme: OrderScheme) -> None:
        """Lock in the chosen scheme and precompute protect/ban sequences.

        Exposed so tests (and callers that skip the roll phase) can drive the
        state machine without the interactive flow.
        """
        self.scheme = scheme
        self._protect_seq = self._compute_seq(
            scheme.protect_first, self.match.ruleset.protects_for
        )
        self._ban_seq = self._compute_seq(
            scheme.ban_first, self.match.ruleset.bans_for, pattern=scheme.ban_pattern
        )
        self.phase = Phase.PROTECT if self._protect_seq else (
            Phase.BAN_1 if self._ban_seq else Phase.PICK
        )

    def set_ranking(self, ranking: list[int]) -> None:
        """Test / override entry point: set the roll ranking directly."""
        self.ranking = list(ranking)
        self._roll_done.set()

    # ------------------------------------------------- sequence precomputation

    def _rank_to_team(self, rank: int) -> int:
        return self.ranking[rank]

    def _compute_seq(self, first_rank: int, count_for, pattern: str = "ABAB") -> list[int]:
        """Round-robin team_indices starting at `first_rank`, each team contributing
        `count_for(team_index)` entries. ABBA swaps each pair in 2-team configs."""
        n = len(self.ranking)
        rank_order = [(first_rank + i) % n for i in range(n)]
        # how many actions each rank owes
        owed = [count_for(self._rank_to_team(r)) for r in rank_order]
        seq: list[int] = []
        i = 0
        while any(o > 0 for o in owed):
            if owed[i] > 0:
                seq.append(self._rank_to_team(rank_order[i]))
                owed[i] -= 1
            i = (i + 1) % n

        if pattern == "ABBA" and n == 2 and len(seq) >= 4:
            # swap every second pair: A B A B -> A B B A
            out = []
            for j in range(0, len(seq), 4):
                chunk = seq[j:j + 4]
                if len(chunk) == 4:
                    out.extend([chunk[0], chunk[1], chunk[3], chunk[2]])
                else:
                    out.extend(chunk)
            seq = out
        return seq

    # --------------------------------------------------------------- state machine

    def next_step(self, match_status) -> tuple[int, Step]:
        needed = self.match.ruleset.wins_needed

        # 1. win check
        for ti, w in enumerate(self._wins):
            if w >= needed:
                self.phase = Phase.DONE
                return (ti, Step.WIN)

        # 2. tiebreaker — only meaningful when needed > 1 (BO1 has no tiebreak)
        if not self._tb_triggered and needed > 1:
            at_brink = [i for i, w in enumerate(self._wins) if w == needed - 1]
            if len(at_brink) >= 2:
                self._tb_triggered = True
                self.phase = Phase.TB
                return (0, Step.OTHER)

        # 3. protects
        if self._protect_cursor < len(self._protect_seq):
            t = self._protect_seq[self._protect_cursor]
            self._protect_cursor += 1
            self.phase = Phase.PROTECT
            return (t, Step.PROTECT)

        # 4. bans (first half when split, full otherwise)
        total_bans = len(self._ban_seq)
        split = self.scheme.split_ban_after_pick if self.scheme else None
        half = total_bans // 2 if split is not None else total_bans
        if self._ban_cursor < half:
            t = self._ban_seq[self._ban_cursor]
            self._ban_cursor += 1
            self.phase = Phase.BAN_1
            return (t, Step.BAN)

        # 5. split bans second half — only after the pick threshold
        if (split is not None
                and self._pick_count >= split
                and self._ban_cursor < total_bans):
            t = self._ban_seq[self._ban_cursor]
            self._ban_cursor += 1
            self.phase = Phase.BAN_2
            return (t, Step.BAN)

        # 6. pick
        t = self.next_picker(match_status)
        self._pick_count += 1
        self.phase = Phase.PICK
        return (t, Step.PICK)

    def next_picker(self, match_status) -> int:
        """Default 2-team rule: strict ABAB alternation starting from scheme.pick_first."""
        if len(self.match.teams) > 2:
            raise NotImplementedError(
                "override next_picker for matches with more than 2 teams"
            )
        assert self.scheme is not None
        n = len(self.match.teams)
        return self._rank_to_team((self.scheme.pick_first + self._pick_count) % n)

    # -------------------------------------------------------------- handlers

    async def handle_pick(self, team_index: int, beatmap_id: int) -> None:
        """Override to track map winners for the win/TB logic."""
        await self.announce_pick(team_index, beatmap_id)
        result = await self.play_map(beatmap_id, team_index, Step.PICK)
        winner = self._map_winner(result) if result else None
        if winner is not None:
            self._wins[winner] += 1
            self._last_map_winner = winner

    async def handle_other(self, team_index: int) -> None:
        """Tiebreaker: flip the TB map to PICKABLE and play it as a pick by the
        loser of the last map (or rank-0 team if no prior map)."""
        tb = next((pm for pm in self.match.pool.flatten() if pm.is_tiebreaker), None)
        if tb is None:
            logger.error("TB triggered but no map has is_tiebreaker=True")
            return
        src = _find_map(self.match, tb.beatmap_id)
        if src is not None:
            src.state = MapState.PICKABLE
        await self.lobby.say("Tiebreaker!")
        picker = (1 - self._last_map_winner) if self._last_map_winner is not None else self._rank_to_team(0)
        await self.handle_pick(picker, tb.beatmap_id)

    # ------------------------------------------------------------ commands

    def _resolve_team(self, token: str) -> int | None:
        """Accept either a team_index (digits) or a normalized team name."""
        if token.isdigit():
            i = int(token)
            return i if 0 <= i < len(self.match.teams) else None
        needle = _normalize(token)
        for i, t in enumerate(self.match.teams):
            if _normalize(t.name) == needle:
                return i
        return None

    async def _dispatch_command(self, cmd: str, args: list[str], source: str) -> bool:
        if cmd == "roll" and args:
            ranking: list[int] = []
            for tok in args:
                i = self._resolve_team(tok)
                if i is None or i in ranking:
                    await self.lobby.say(f"Unknown or duplicate team: {tok}")
                    return True
                ranking.append(i)
            if len(ranking) != len(self.match.teams):
                await self.lobby.say(
                    f"Expected {len(self.match.teams)} teams in ranking, got {len(ranking)}"
                )
                return True
            self.ranking = ranking
            self._roll_done.set()
            names = ", ".join(self.match.teams[i].name for i in ranking)
            await self.lobby.say(f"Ranking set: {names}")
            return True

        if cmd == "order" and args:
            try:
                n = int(args[0])
            except ValueError:
                await self.lobby.say("Usage: >order <n>")
                return True
            if not (1 <= n <= len(self.schemes)):
                await self.lobby.say(f"Scheme out of range (1..{len(self.schemes)})")
                return True
            self.scheme = self.schemes[n - 1]
            self._order_done.set()
            await self.lobby.say(f"Scheme: {self.scheme.name}")
            return True

        if cmd == "phase":
            await self.lobby.say(
                f"phase={self.phase.name} "
                f"protects={self._protect_cursor}/{len(self._protect_seq)} "
                f"bans={self._ban_cursor}/{len(self._ban_seq)} "
                f"picks={self._pick_count} wins={self._wins}"
            )
            return True

        return await super()._dispatch_command(cmd, args, source)

    # ------------------------------------------------------------ roll phase

    async def _run_roll_phase(self) -> None:
        self.phase = Phase.ROLL
        self._rolls = {}
        await self.lobby.say(
            f"All teams, please !roll. You have {self.roll_timeout}s — "
            "ref can override with >roll <team> <team> [...]."
        )

        def on_msg(msg) -> None:
            if getattr(msg.user, "username", None) != "BanchoBot":
                return
            m = _ROLL_RE.match(msg.message)
            if not m:
                return
            user = _normalize(m.group("user"))
            value = int(m.group("n"))
            for ti, team in enumerate(self.match.teams):
                if any(_normalize(p.username) == user for p in team.players):
                    if ti in self._rolls:
                        return  # first roll per team wins
                    self._rolls[ti] = value
                    logger.info("roll: %s (team %d) = %d", user, ti, value)
                    if (len(self._rolls) == len(self.match.teams)
                            and not self._roll_done.is_set()):
                        self.ranking = sorted(
                            self._rolls.keys(),
                            key=lambda i: -self._rolls[i],
                        )
                        self._roll_done.set()
                    return

        self.lobby.channel.on("message", on_msg)
        try:
            try:
                await asyncio.wait_for(self._roll_done.wait(), self.roll_timeout)
            except asyncio.TimeoutError:
                if self._rolls:
                    ranked = sorted(self._rolls.keys(), key=lambda i: -self._rolls[i])
                    missing = [i for i in range(len(self.match.teams)) if i not in self._rolls]
                    self.ranking = ranked + missing
                    await self.lobby.say(
                        "Roll timeout — using partial results. Ref can override with >roll."
                    )
                else:
                    self.ranking = list(range(len(self.match.teams)))
                    await self.lobby.say(
                        "No rolls received — defaulting to team order. Ref can override with >roll."
                    )
        finally:
            self.lobby.channel.remove_listener("message", on_msg)

    # ------------------------------------------------------------ order phase

    async def _run_order_phase(self) -> None:
        self.phase = Phase.ORDER
        if len(self.schemes) == 1:
            self.scheme = self.schemes[0]
            return
        winner = self.match.teams[self.ranking[0]].name
        options = " | ".join(f"{i}) {s.name}" for i, s in enumerate(self.schemes, start=1))
        await self.lobby.say(f"{winner}, choose a scheme with >order <n>: {options}")
        await self._order_done.wait()

    # --------------------------------------------------------------- pre-loop

    async def _pre_loop(self) -> None:
        if self.ranking is None:
            await self._run_roll_phase()
        if self.scheme is None:
            await self._run_order_phase()
        self.commit_scheme(self.scheme)

    def _get_state(self) -> dict:
        state = super()._get_state()
        state["phase"] = self.phase.name
        state["wins"] = list(self._wins)
        return state

    def _map_winner(self, result: MatchResult) -> int | None:
        """Team_index whose players' scores sum highest. None on tie/empty."""
        if result is None or not result.scores:
            return None
        totals = [0] * len(self.match.teams)
        u2t: dict[str, int] = {}
        for i, team in enumerate(self.match.teams):
            for p in team.players:
                u2t[_normalize(p.username)] = i
        for pr in result.scores:
            ti = u2t.get(_normalize(pr.username))
            if ti is not None and pr.passed:
                totals[ti] += pr.score
        top = max(totals)
        if top == 0:
            return None
        winners = [i for i, t in enumerate(totals) if t == top]
        return winners[0] if len(winners) == 1 else None
