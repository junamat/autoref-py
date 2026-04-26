"""Run the Z-Sum leaderboard against a real qualifiers fixture.

Loads tests/fixtures/qualifiers_4wc_scores.csv (376 score rows from the
4WC 2025 Open Qualifiers spreadsheet) and prints our computed leaderboard
side-by-side with the sheet's published z-sum values.

Run from the repo root:
    python scripts/stats_poc.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from autoref.core.stats import z_sum_leaderboard, exclude_failed


FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def main() -> None:
    scores = pd.read_csv(FIXTURES / "qualifiers_4wc_scores.csv")
    expected = pd.read_csv(FIXTURES / "qualifiers_4wc_expected.csv")

    # The sheet uses `modded_score` (mod multipliers applied; mostly == score for this stage).
    # Pass that into stats.py via the `score` column the function expects.
    df = scores.rename(columns={"score": "raw_score", "modded_score": "score"})

    print("=" * 72)
    print("Sheet settings: count_failed=True → matches our default include_all")
    print("=" * 72)
    leaderboard = z_sum_leaderboard(df).head(15)

    cmp = leaderboard.merge(expected, on="username", how="left")
    cmp["delta"] = (cmp["z_sum"] - cmp["z_sum_sheet"]).round(6)
    print(cmp[["username", "maps_played", "z_sum", "z_sum_sheet", "delta"]].to_string(index=False))

    print()
    print("=" * 72)
    print("Same data with include=exclude_failed (drop failed rows from population)")
    print("=" * 72)
    leaderboard2 = z_sum_leaderboard(df, include=exclude_failed).head(15)
    print(leaderboard2[["username", "maps_played", "z_sum"]].to_string(index=False))


if __name__ == "__main__":
    main()
