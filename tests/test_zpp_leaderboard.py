"""Tests for Z-PP leaderboard formula.

Expected formula:
  1. For each player, keep best pp per (player, map) (deduplicated by max pp).
  2. For each map compute: z_pp = (player_pp - map_mean_pp) / map_std_pp
     (sample std, ddof=1; std=0 or NaN → z_pp=0).
  3. Per-player score = sum (or mean) of z_pp values across all maps played.
"""
import math
from unittest.mock import patch

import pandas as pd
import pytest

from autoref.core.stats.leaderboards.pp import z_pp_leaderboard


def _scores(rows):
    out = []
    for r in rows:
        full = {
            "passed": True,
            "username": str(r.get("user_id")),
            "mods": "[]",
            "accuracy": 1.0,
            "max_combo": 0,
            "nmiss": 0,
        }
        full.update(r)
        out.append(full)
    return pd.DataFrame(out)


def _mock_augment_by_key(pp_map: dict):
    """Returns augment_pp mock that assigns pp from {(user_id, beatmap_id): pp}."""
    async def _augment(scores, *, concurrency=8, db=None):
        df = scores.copy()
        df["pp"] = df.apply(
            lambda r: pp_map.get((int(r["user_id"]), int(r["beatmap_id"])), float("nan")),
            axis=1,
        )
        return df
    return _augment


def _mock_augment_by_score(score_to_pp: dict):
    """Returns augment_pp mock that assigns pp from {score_value: pp}."""
    async def _augment(scores, *, concurrency=8, db=None):
        df = scores.copy()
        df["pp"] = df["score"].map(score_to_pp)
        return df
    return _augment


# ----------------------------------------------------------------- edge cases

@pytest.mark.asyncio
async def test_z_pp_empty():
    df = pd.DataFrame(columns=["user_id", "username", "score", "passed", "beatmap_id"])
    out = await z_pp_leaderboard(df)
    assert out.empty
    assert "z_pp" in out.columns


@pytest.mark.asyncio
async def test_z_pp_all_nan_pp_returns_empty():
    """augment_pp returns NaN pp for all rows → result empty."""
    rows = [{"user_id": 1, "beatmap_id": 10, "score": 1}]
    df = _scores(rows)
    with patch("autoref.core.stats.leaderboards.pp.augment_pp", _mock_augment_by_key({})):
        out = await z_pp_leaderboard(df)
    assert out.empty


# ----------------------------------------------------------------- single-player

@pytest.mark.asyncio
async def test_z_pp_single_player_yields_zero():
    """One player on a map → std=NaN → fillna(0)."""
    pp_map = {(1, 10): 500.0}
    rows = [{"user_id": 1, "beatmap_id": 10, "score": 1}]
    df = _scores(rows)
    with patch("autoref.core.stats.leaderboards.pp.augment_pp", _mock_augment_by_key(pp_map)):
        out = await z_pp_leaderboard(df)
    assert out.iloc[0]["z_pp"] == pytest.approx(0.0)


# ----------------------------------------------------------------- equal pp

@pytest.mark.asyncio
async def test_z_pp_equal_pp_yields_zero():
    """All players same pp on every map → z=0."""
    pp_map = {(1, 10): 300.0, (2, 10): 300.0, (1, 20): 200.0, (2, 20): 200.0}
    rows = [
        {"user_id": 1, "beatmap_id": 10, "score": 1},
        {"user_id": 2, "beatmap_id": 10, "score": 2},
        {"user_id": 1, "beatmap_id": 20, "score": 3},
        {"user_id": 2, "beatmap_id": 20, "score": 4},
    ]
    df = _scores(rows)
    with patch("autoref.core.stats.leaderboards.pp.augment_pp", _mock_augment_by_key(pp_map)):
        out = await z_pp_leaderboard(df)
    assert all(v == pytest.approx(0.0) for v in out["z_pp"])


# ----------------------------------------------------------------- math correctness

@pytest.mark.asyncio
async def test_z_pp_basic_three_players_two_maps():
    """3 players × 2 maps, known pp → verify z_pp sums and ranking.

    Player 1: A=100pp, B=200pp  → z_A=-1.0, z_B=+1.0  → total=0.0
    Player 2: A=150pp, B=100pp  → z_A=0.0,  z_B=-1.0  → total=-1.0
    Player 3: A=200pp, B=150pp  → z_A=+1.0, z_B=0.0   → total=+1.0

    Map A: mean=150, std=sqrt(((100-150)²+(0)+(200-150)²)/2)=50
    Map B: mean=150, std=50
    """
    pp_map = {
        (1, 10): 100.0, (1, 20): 200.0,
        (2, 10): 150.0, (2, 20): 100.0,
        (3, 10): 200.0, (3, 20): 150.0,
    }
    rows = [
        {"user_id": 1, "beatmap_id": 10, "score": 1},
        {"user_id": 1, "beatmap_id": 20, "score": 2},
        {"user_id": 2, "beatmap_id": 10, "score": 3},
        {"user_id": 2, "beatmap_id": 20, "score": 4},
        {"user_id": 3, "beatmap_id": 10, "score": 5},
        {"user_id": 3, "beatmap_id": 20, "score": 6},
    ]
    df = _scores(rows)
    with patch("autoref.core.stats.leaderboards.pp.augment_pp", _mock_augment_by_key(pp_map)):
        out = await z_pp_leaderboard(df)
    out_idx = out.set_index("user_id")
    assert out_idx.loc[3, "z_pp"] == pytest.approx(1.0)
    assert out_idx.loc[1, "z_pp"] == pytest.approx(0.0)
    assert out_idx.loc[2, "z_pp"] == pytest.approx(-1.0)
    assert list(out["user_id"]) == [3, 1, 2]  # descending order


# ----------------------------------------------------------------- dedup

@pytest.mark.asyncio
async def test_z_pp_deduplicates_to_best_pp():
    """Player with two attempts on same map — highest pp wins.

    Player 1: attempt with pp=100, attempt with pp=200 → keeps pp=200
    Player 2: single attempt pp=150
    mean=175, std=sqrt(((200-175)²+(150-175)²)/1)=sqrt(1250)≈35.36
    z_pp[1]=(200-175)/std≈+0.707, z_pp[2]=(150-175)/std≈-0.707
    """
    score_to_pp = {900_000: 100.0, 800_000: 200.0, 850_000: 150.0}
    rows = [
        {"user_id": 1, "beatmap_id": 10, "score": 900_000},
        {"user_id": 1, "beatmap_id": 10, "score": 800_000},
        {"user_id": 2, "beatmap_id": 10, "score": 850_000},
    ]
    df = _scores(rows)
    with patch("autoref.core.stats.leaderboards.pp.augment_pp", _mock_augment_by_score(score_to_pp)):
        out = await z_pp_leaderboard(df)
    out_idx = out.set_index("user_id")
    expected_std = math.sqrt(1250)
    assert out_idx.loc[1, "z_pp"] == pytest.approx(25.0 / expected_std)
    assert out_idx.loc[2, "z_pp"] == pytest.approx(-25.0 / expected_std)


# ----------------------------------------------------------------- aggregate

@pytest.mark.asyncio
async def test_z_pp_aggregate_mean():
    """aggregate='mean' divides by maps_played instead of summing."""
    pp_map = {
        (1, 10): 100.0, (1, 20): 200.0,
        (2, 10): 150.0, (2, 20): 100.0,
        (3, 10): 200.0, (3, 20): 150.0,
    }
    rows = [
        {"user_id": 1, "beatmap_id": 10, "score": 1},
        {"user_id": 1, "beatmap_id": 20, "score": 2},
        {"user_id": 2, "beatmap_id": 10, "score": 3},
        {"user_id": 2, "beatmap_id": 20, "score": 4},
        {"user_id": 3, "beatmap_id": 10, "score": 5},
        {"user_id": 3, "beatmap_id": 20, "score": 6},
    ]
    df = _scores(rows)
    with patch("autoref.core.stats.leaderboards.pp.augment_pp", _mock_augment_by_key(pp_map)):
        out = await z_pp_leaderboard(df, aggregate="mean")
    out_idx = out.set_index("user_id")
    assert out_idx.loc[1, "z_pp"] == pytest.approx(0.0)       # (−1+1)/2=0
    assert out_idx.loc[3, "z_pp"] == pytest.approx(0.5)       # (1+0)/2=0.5
    assert out_idx.loc[2, "z_pp"] == pytest.approx(-0.5)      # (0-1)/2=-0.5
