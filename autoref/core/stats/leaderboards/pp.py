from __future__ import annotations

import asyncio
import json as _json

import pandas as pd

from .._shared import _empty, _finish
from ..predicates import ScorePredicate, include_all


def _row_mods(row) -> list[str]:
    """Decode the JSON mods field on a score row to a list of acronyms."""
    raw = row.get("mods") if isinstance(row, dict) else row["mods"]
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(m).upper() for m in raw if m]
    try:
        parsed = _json.loads(raw)
        return [str(m).upper() for m in parsed if m]
    except Exception:
        return []


async def augment_pp(scores: pd.DataFrame, *, concurrency: int = 8, db=None) -> pd.DataFrame:
    """Return a copy of `scores` with a `pp` column populated via rosu-pp-py.

    If `scores` already carries a non-null `pp` value for a row, it's reused
    and not recomputed. Rows where pp can't be computed (rosu-pp-py missing,
    .osu fetch failed, parse error) get pp = NaN. Identical
    (bid, mods, accuracy, max_combo, misses) plays are computed once and
    reused within the call.

    If `db` is provided (a `MatchDatabase`), newly-computed pp values are
    persisted back to `game_scores.pp` (keyed by the row's `id` column),
    making subsequent calls a DB read instead of a recompute.
    """
    from ...pp_calc import compute_pp, current_pp_version

    if scores is None or scores.empty:
        out = scores.copy() if scores is not None else pd.DataFrame()
        out["pp"] = pd.Series(dtype=float)
        return out

    df = scores.copy()
    if "pp" not in df.columns:
        df["pp"] = pd.NA
    cur_ver = current_pp_version()
    sem = asyncio.Semaphore(concurrency)
    cache: dict[tuple, float | None] = {}
    new_writes: list[tuple[int, float | None, str | None]] = []

    async def _one(idx, row):
        existing = row.get("pp", None)
        existing_ver = row.get("pp_version", None) if "pp_version" in df.columns else None
        if existing is not None and pd.notna(existing):
            same_ver = (
                cur_ver is not None
                and existing_ver is not None
                and pd.notna(existing_ver)
                and str(existing_ver) == str(cur_ver)
            )
            if same_ver:
                return idx, float(existing), False
        bid = int(row["beatmap_id"])
        mods = tuple(sorted(_row_mods(row)))
        acc = float(row.get("accuracy", 0.0) or 0.0)
        if acc <= 1.0:
            acc *= 100.0
        combo = int(row.get("max_combo", 0) or 0)
        misses = int(row.get("nmiss", 0) or 0)
        key = (bid, mods, round(acc, 2), combo, misses)
        if key in cache:
            return idx, cache[key], False
        async with sem:
            pp_result = await compute_pp(
                bid,
                mods=list(mods),
                accuracy=acc,
                max_combo=combo or None,
                misses=misses,
            )
        pp = pp_result.value if pp_result else None
        cache[key] = pp
        return idx, pp, True

    results = await asyncio.gather(*(_one(i, r) for i, r in df.iterrows()))
    df["pp"] = pd.Series({i: pp for i, pp, _ in results}, dtype="float64")

    if db is not None and "id" in df.columns:
        for idx, pp, was_new in results:
            if not was_new or pp is None:
                continue
            sid = df.at[idx, "id"]
            if pd.isna(sid):
                continue
            new_writes.append((int(sid), float(pp), cur_ver))
        if new_writes:
            try:
                db.update_pp_bulk(new_writes)
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning("augment_pp: failed to persist pp: %s", exc)

    return df


def _prep_pp(df: pd.DataFrame) -> pd.DataFrame | None:
    """Drop rows without a usable pp value, dedupe to best pp per (player, map)."""
    if df.empty or "pp" not in df.columns:
        return None
    df = df.dropna(subset=["pp"])
    if df.empty:
        return None
    return (df.sort_values("pp", ascending=False)
              .drop_duplicates(subset=["user_id", "beatmap_id"]))


async def pp_leaderboard(
    scores: pd.DataFrame,
    *,
    include: ScorePredicate = include_all,
    aggregate: str = "sum",
    db=None,
) -> pd.DataFrame:
    """Per-player pp leaderboard. Requires rosu-pp-py."""
    if scores.empty:
        return _empty("pp")
    filt = scores.loc[scores.apply(include, axis=1)].copy()
    if filt.empty:
        return _empty("pp")
    aug = await augment_pp(filt, db=db)
    df = _prep_pp(aug)
    if df is None:
        return _empty("pp")
    return _finish(df, "username", "pp", ascending=False, aggregate=aggregate)


async def z_pp_leaderboard(
    scores: pd.DataFrame,
    *,
    include: ScorePredicate = include_all,
    aggregate: str = "sum",
    db=None,
) -> pd.DataFrame:
    """Per-player Z-PP leaderboard.

    Formula:
      1. Keep best pp per (player, map).
      2. z_pp = (player_pp − map_mean_pp) / map_std_pp  (sample std, ddof=1;
         std=0 or NaN → z_pp=0).
      3. Aggregate z_pp across maps per player (sum or mean).
    """
    if scores.empty:
        return _empty("z_pp")
    filt = scores.loc[scores.apply(include, axis=1)].copy()
    if filt.empty:
        return _empty("z_pp")
    aug = await augment_pp(filt, db=db)
    df = _prep_pp(aug)
    if df is None:
        return _empty("z_pp")

    map_stats = df.groupby("beatmap_id")["pp"].agg(["mean", "std"])
    df = df.join(map_stats, on="beatmap_id")
    df["z_pp"] = ((df["pp"] - df["mean"]) / df["std"]).fillna(0.0)
    return _finish(df, "username", "z_pp", ascending=False, aggregate=aggregate)
