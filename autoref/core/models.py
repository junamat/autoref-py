from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
import asyncio

import aiosu
import pandas as pd

from .enums import WinCondition, MapState, Step


@dataclass
class OrderScheme:
    """Declarative bracket-match order. Roles are roll ranks (0 = roll winner).

    For the common 2-team case, "first" means the role that acts before the other;
    subsequent actions round-robin by rank. ABAB rotates straight; ABBA rotates
    and reverses within each doubled step (2-team only — ignored for N>2).

    `split_ban_after_pick` triggers a second ban round after N picks; half the
    total bans run before picks, the remaining half after the threshold.
    """
    name: str
    protect_first: int = 0
    ban_first: int = 0
    pick_first: int = 0
    ban_pattern: str = "ABAB"
    split_ban_after_pick: int | None = None


@dataclass
class Timers:
    pick: int = 120        # seconds a team has to pick
    ban: int = 120         # seconds a team has to ban
    protect: int = 120     # seconds a team has to protect
    ready_up: int = 90     # !mp timer after map is set; players ready up during this window
    start_map: int = 5     # delay passed to !mp start after ready; auto-start countdown
    force_start: int = 10  # delay used by >go / >startmap for manual starts
    between_maps: int = 5  # asyncio.sleep buffer after a map ends, before the bot moves on
    closing: int = 30      # seconds between win announcement and lobby close


NO_MODS = object()  # sentinel: explicitly no extra mods, bypasses pool/name inference

# Extra mods only — NF is excluded because it is applied room-wide via Ruleset.enforced_mods.
# play_map merges these with enforced_mods before calling set_mods.
_MOD_INFERENCE: dict[str, str] = {
    "HD": "HD",
    "HR": "HR",
    "DT": "DT",
    "FM": "Freemod",
}


def _canonical_mods(mods) -> list[str]:
    """Normalize mod input → sorted list of 2-char tokens, NF excluded.

    Accepts: aiosu Mods instance, str like "HDHR" / "HD HR", iterable of tokens.
    """
    if mods is None:
        return []
    if isinstance(mods, str):
        s = mods.replace(" ", "")
        toks = [s[i:i + 2].upper() for i in range(0, len(s), 2) if s[i:i + 2]]
    else:
        toks = []
        for m in mods:
            if hasattr(m, "value") or hasattr(m, "name"):
                toks.append(getattr(m, "short_name", None) or m.name if hasattr(m, "name") else str(m))
            else:
                toks.append(str(m))
        toks = [t.upper() for t in toks if t]
    return sorted(t for t in toks if t and t != "NF")


def apply_score_multiplier(score: int | float, mods, multipliers: dict[str, float] | None) -> float:
    """Apply mod multipliers to a raw score.

    Resolution: exact-combo key (sorted concat e.g. "HDHR") wins; otherwise the
    score is multiplied by each per-mod entry cumulatively. Missing mods → 1.0.
    Returns the adjusted score (float — caller rounds/casts as needed).
    """
    if not multipliers or score is None:
        return float(score) if score is not None else 0.0
    toks = _canonical_mods(mods)
    if not toks:
        return float(score)
    combo_key = "".join(toks)
    if combo_key in multipliers:
        return float(score) * float(multipliers[combo_key])
    out = float(score)
    for t in toks:
        if t in multipliers:
            out *= float(multipliers[t])
    return out


def _merge_multipliers(*dicts: "dict[str, float] | None") -> dict[str, float]:
    """Merge multiplier dicts; later overrides earlier, per-key."""
    out: dict[str, float] = {}
    for d in dicts:
        if d:
            out.update(d)
    return out


class PlayableMap:
    def __init__(
        self,
        beatmap_id: int,
        mods=None,
        win_condition: WinCondition = WinCondition.INHERIT,
        name: str = None,
        is_tiebreaker: bool = False,
        score_multipliers: dict[str, float] | None = None,
    ):
        self.beatmap_id = beatmap_id
        self.beatmap = None
        self.mods = mods
        self.win_condition = win_condition
        self.name = name
        self.is_tiebreaker = is_tiebreaker
        self.score_multipliers = score_multipliers
        self.state = MapState.PICKABLE
        # Set by Pool.flatten — list of pool multiplier dicts outer→inner.
        self._pool_mult_chain: list[dict[str, float]] = []

    def effective_multipliers(self, ruleset_mults: dict[str, float] | None = None) -> dict[str, float]:
        """Resolve effective multiplier table by merging ruleset → pool chain → map.
        Most-specific wins (map > inner pool > outer pool > ruleset)."""
        return _merge_multipliers(ruleset_mults, *self._pool_mult_chain, self.score_multipliers)

    def effective_mods(self, pool_mods=None):
        """Resolve extra mods with priority: explicit (or NO_MODS) > pool_mods > name inference.

        Returns None when no extra mods apply (e.g. NM maps).
        play_map is responsible for combining the result with Ruleset.enforced_mods.
        """
        if self.mods is NO_MODS:
            return None
        if self.mods is not None:
            return self.mods
        pm = pool_mods if pool_mods is not None else getattr(self, "_pool_mods", None)
        if pm is NO_MODS:
            return None
        if pm is not None:
            return pm
        if self.name:
            prefix = self.name[:2].upper()
            inferred = _MOD_INFERENCE.get(prefix)
            if inferred:
                return aiosu.models.mods.Mods(inferred)
        return None

    @classmethod
    async def create(
        cls,
        beatmap_id: int,
        mods: aiosu.models.mods.Mods = None,
        win_condition: WinCondition = WinCondition.INHERIT,
        name: str = None,
        is_tiebreaker: bool = False,
        client: "aiosu.v2.Client | None" = None,
    ) -> "PlayableMap":
        instance = cls(beatmap_id, mods, win_condition, name, is_tiebreaker)
        if client is not None:
            instance.beatmap = await client.get_beatmap(beatmap_id)
        else:
            from ..client import make_client
            async with make_client() as c:
                instance.beatmap = await c.get_beatmap(beatmap_id)
        return instance


class Pool:
    def __init__(self, name: str, *maps: "Pool | PlayableMap",
                 order: "Callable[[list[PlayableMap]], list[PlayableMap]] | None" = None,
                 score_multipliers: dict[str, float] | None = None):
        self.name = name
        self.maps = list(maps)
        self.order = order  # optional callable to reorder the flattened list
        self.score_multipliers = score_multipliers

    def flatten(self, _pool_mods=None, _mult_chain: list | None = None) -> "list[PlayableMap]":
        """Depth-first flatten, propagating pool mods, multiplier chain, and order."""
        chain = list(_mult_chain or [])
        if self.score_multipliers:
            chain = chain + [self.score_multipliers]
        result = []
        for item in self.maps:
            if isinstance(item, Pool):
                result.extend(item.flatten(_pool_mods=_pool_mods, _mult_chain=chain))
            else:
                pm = PlayableMap(item.beatmap_id, item.mods, item.win_condition,
                                 item.name, item.is_tiebreaker,
                                 score_multipliers=item.score_multipliers)
                pm.beatmap = item.beatmap
                pm._pool_mods = _pool_mods
                pm._pool_mult_chain = chain
                result.append(pm)
        if self.order:
            result = self.order(result)
        return result


class ModdedPool(Pool):
    def __init__(self, name: str, mods: aiosu.models.mods.Mods, *maps: "Pool | PlayableMap",
                 order=None, score_multipliers: dict[str, float] | None = None):
        super().__init__(name, *maps, order=order, score_multipliers=score_multipliers)
        self.mods = mods

    def flatten(self, _pool_mods=None, _mult_chain: list | None = None) -> "list[PlayableMap]":
        # own mods take priority over parent pool mods
        return super().flatten(_pool_mods=self.mods, _mult_chain=_mult_chain)


class Team:
    def __init__(self, name: str):
        self.name = name
        self.players: list = []

    @classmethod
    async def create(cls, name: str, *player_ids: int,
                     client: "aiosu.v2.Client | None" = None) -> "Team":
        instance = cls(name)
        if client is not None:
            results = await asyncio.gather(
                *(client.get_user(pid) for pid in player_ids)
            )
        else:
            from ..client import make_client
            async with make_client() as c:
                results = await asyncio.gather(
                    *(c.get_user(pid) for pid in player_ids)
                )
        instance.players = list(results)
        return instance

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([vars(p) for p in self.players])


class Ruleset:
    def __init__(
        self,
        vs: int,
        gamemode: aiosu.models.Gamemode,
        win_condition: WinCondition = WinCondition.SCORE_V2,
        enforced_mods: str = "NF",
        team_mode: int = 2,  # 0=HeadToHead, 2=TeamVs
        best_of: int = 1,
        bans_per_team: "int | list[int]" = 0,
        protects_per_team: "int | list[int]" = 0,
        schemes: "list[OrderScheme] | None" = None,
        score_multipliers: dict[str, float] | None = None,
    ):
        self.vs = vs
        self.gamemode = gamemode
        self.win_condition = win_condition
        self.enforced_mods = aiosu.models.mods.Mods(enforced_mods) if enforced_mods else None
        self.team_mode = team_mode
        self.best_of = best_of
        # int = symmetric (same for every team); list = per-team indexed
        self.bans_per_team = bans_per_team
        self.protects_per_team = protects_per_team
        self.schemes = schemes
        self.score_multipliers = score_multipliers

    @property
    def wins_needed(self) -> int:
        return self.best_of // 2 + 1

    def bans_for(self, team_index: int) -> int:
        v = self.bans_per_team
        return v if isinstance(v, int) else v[team_index]

    def protects_for(self, team_index: int) -> int:
        v = self.protects_per_team
        return v if isinstance(v, int) else v[team_index]


class Match:
    _STATUS_COLUMNS = ["turn", "team_index", "step", "beatmap_id", "timestamp"]

    def __init__(
        self,
        ruleset: Ruleset,
        pool: Pool,
        next_step: Callable[[pd.DataFrame], tuple[int, Step]],
        *teams: Team,
        pool_id: str | None = None,
        round_name: str | None = None,
    ):
        self.ruleset = ruleset
        self.pool = pool
        self.next_step = next_step  # next_step(match_status) -> (team_index, Step)
        self.teams = teams
        self.match_status = pd.DataFrame(columns=self._STATUS_COLUMNS)
        self.match_id: int | None = None  # assigned by MatchDatabase after persisting
        # Tournament context — used by /stats filters; either may be None for ad-hoc matches.
        self.pool_id = pool_id
        self.round_name = round_name
        # API-enriched per-player score data, populated asynchronously by ScoreFetcher.
        # List of (turn, beatmap_id, list[score_dict]).
        self.game_scores: list[tuple[int, int, list[dict]]] = []

    def add_game_scores(self, turn: int, beatmap_id: int, scores: list[dict]) -> None:
        self.game_scores.append((turn, beatmap_id, scores))

    def record_action(self, team_index: int, step: Step, beatmap_id: int) -> None:
        row = {
            "turn": len(self.match_status),
            "team_index": team_index,
            "step": step.name,
            "beatmap_id": beatmap_id,
            "timestamp": pd.Timestamp.now(),
        }
        self.match_status = pd.concat(
            [self.match_status, pd.DataFrame([row])],
            ignore_index=True,
        )

    def save(self, path: str | Path) -> None:
        self.match_status.to_csv(path, index=False)

    def resume(self, path: str | Path) -> None:
        self.match_status = pd.read_csv(path, parse_dates=["timestamp"])


# ── pool query helpers ────────────────────────────────────────────────────────

def _normalize(name: str) -> str:
    return name.replace(" ", "_").casefold()


def _find_map(match: "Match", beatmap_id: int) -> "PlayableMap | None":
    stack = list(match.pool.maps)
    while stack:
        item = stack.pop()
        if isinstance(item, Pool):
            stack.extend(item.maps)
        elif item.beatmap_id == beatmap_id:
            return item
    return None


def _find_map_by_input(match: "Match", text: str) -> "PlayableMap | None":
    """Find a map by name/code. Only returns PICKABLE maps (ban path)."""
    needle = _normalize(text)
    stack = list(match.pool.maps)
    while stack:
        item = stack.pop()
        if isinstance(item, Pool):
            stack.extend(item.maps)
        elif item.name and _normalize(item.name) == needle:
            if item.state == MapState.PICKABLE:
                return item
    return None


def _find_map_by_input_pick(match: "Match", text: str) -> "PlayableMap | None":
    """Like _find_map_by_input but also allows PROTECTED maps (pick/protect path)."""
    needle = _normalize(text)
    stack = list(match.pool.maps)
    while stack:
        item = stack.pop()
        if isinstance(item, Pool):
            stack.extend(item.maps)
        elif item.name and _normalize(item.name) == needle:
            if item.state in (MapState.PICKABLE, MapState.PROTECTED):
                return item
    return None
