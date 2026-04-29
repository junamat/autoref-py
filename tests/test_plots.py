"""Smoke tests for autoref.plots — ensure each renderer returns non-empty bytes
for representative inputs and edge cases. Skipped if matplotlib/scipy aren't installed.
"""
import pandas as pd
import pytest

plots = pytest.importorskip("autoref.plots")


def _scores(rows):
    return pd.DataFrame(rows, columns=["user_id", "username", "beatmap_id", "score", "passed"])


def _map_stats(rows):
    return pd.DataFrame(rows, columns=["beatmap_id", "step", "count"])


def _is_png(b: bytes) -> bool:
    return b.startswith(b"\x89PNG\r\n\x1a\n")


def _is_svg(b: bytes) -> bool:
    return b.lstrip().startswith(b"<?xml") or b.lstrip().startswith(b"<svg")


# ── score_distribution ───────────────────────────────────────────────────────

def test_score_distribution_png():
    df = _scores([
        (1, "alice", 100, 800_000, 1),
        (2, "bob",   100, 850_000, 1),
        (3, "cara",  100, 900_000, 1),
        (4, "dan",   100, 920_000, 1),
        (5, "eli",   100, 880_000, 1),
        (6, "fae",   100, 830_000, 1),
        (7, "gus",   100, 50_000,  0),  # fail, filtered out
    ])
    out = plots.score_distribution(df, beatmap_id=100, fmt="png")
    assert _is_png(out)
    assert len(out) > 1000


def test_score_distribution_svg():
    df = _scores([(i, f"u{i}", 100, 700_000 + i * 1_000, 1) for i in range(20)])
    out = plots.score_distribution(df, beatmap_id=100, fmt="svg")
    assert _is_svg(out)


def test_score_distribution_empty_returns_image():
    df = _scores([])
    out = plots.score_distribution(df, beatmap_id=100, fmt="png")
    assert _is_png(out)  # placeholder image, not an exception


def test_score_distribution_single_score():
    df = _scores([(1, "alice", 100, 800_000, 1)])
    # n=1 → KDE skipped, hist still drawn; should not raise
    out = plots.score_distribution(df, beatmap_id=100, fmt="png")
    assert _is_png(out)


def test_score_distribution_zero_variance():
    df = _scores([(i, f"u{i}", 100, 800_000, 1) for i in range(5)])
    # all identical → std=0, KDE skipped; should not raise
    out = plots.score_distribution(df, beatmap_id=100, fmt="png")
    assert _is_png(out)


# ── pickban_heat ─────────────────────────────────────────────────────────────

def test_pickban_heat_png():
    df = _map_stats([
        (100, "PICK",    5),
        (100, "BAN",     2),
        (100, "PROTECT", 1),
        (101, "PICK",    3),
        (101, "BAN",     4),
        (102, "PROTECT", 2),
    ])
    out = plots.pickban_heat(df, fmt="png")
    assert _is_png(out)


def test_pickban_heat_empty():
    out = plots.pickban_heat(_map_stats([]), fmt="png")
    assert _is_png(out)


def test_pickban_heat_partial_columns():
    # only PICK actions present
    df = _map_stats([(100, "PICK", 5), (101, "PICK", 3)])
    out = plots.pickban_heat(df, fmt="png")
    assert _is_png(out)


# ── consistency_scatter ──────────────────────────────────────────────────────

def test_consistency_scatter_png():
    rows = []
    for uid in range(1, 6):
        for bid in (100, 101, 102):
            rows.append((uid, f"u{uid}", bid, 700_000 + uid * 30_000 + bid * 100, 1))
    out = plots.consistency_scatter(_scores(rows), fmt="png")
    assert _is_png(out)


def test_consistency_scatter_empty():
    out = plots.consistency_scatter(_scores([]), fmt="png")
    assert _is_png(out)


def test_consistency_scatter_svg():
    rows = [(uid, f"u{uid}", 100 + (uid % 3), 800_000 + uid * 1_000, 1) for uid in range(1, 11)]
    out = plots.consistency_scatter(_scores(rows), fmt="svg")
    assert _is_svg(out)


# ── registry ─────────────────────────────────────────────────────────────────

def test_registry_keys():
    assert set(plots.PLOTS) == {"score_distribution", "pickban_heat", "consistency_scatter"}
