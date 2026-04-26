"""Seed matches.db with the 4WC 2025 Open Qualifiers fixture.

Inserts one synthetic match per unique mp_id in the fixture CSV, then
populates game_scores so /stats has data to display.

Usage:
    python scripts/seed_db.py [--db matches.db]
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
CSV = FIXTURES / "qualifiers_4wc_scores.csv"


def seed(db_path: str) -> None:
    df = pd.read_csv(CSV)

    conn = sqlite3.connect(db_path)

    # ensure schema exists
    from autoref.core.storage import MatchDatabase
    MatchDatabase(db_path).close()

    for mp_id, group in df.groupby("match_id"):
        # skip if already seeded
        existing = conn.execute(
            "SELECT match_id FROM matches WHERE winner_team = ?", (f"seed:{mp_id}",)
        ).fetchone()
        if existing:
            print(f"  skip mp/{mp_id} (already seeded)")
            continue

        cur = conn.execute(
            "INSERT INTO matches (ruleset_vs, gamemode, win_condition, best_of, "
            "bans_per_team, protects_per_team, winner_team) VALUES (?,?,?,?,?,?,?)",
            (1, "osu", "SCORE_V2", 1, "0", "0", f"seed:{mp_id}"),
        )
        match_id = cur.lastrowid

        conn.execute(
            "INSERT INTO match_teams VALUES (?,?,?)", (match_id, 0, "qualifiers")
        )

        # one match_action per unique beatmap so map stats work
        for turn, (beatmap_id, _) in enumerate(group.groupby("beatmap_id", sort=False)):
            conn.execute(
                "INSERT INTO match_actions (match_id, turn, team_index, step, beatmap_id, timestamp) "
                "VALUES (?,?,?,?,?,CURRENT_TIMESTAMP)",
                (match_id, turn, 0, "PICK", int(beatmap_id)),
            )

        for turn, (beatmap_id, map_group) in enumerate(group.groupby("beatmap_id", sort=False)):
            for _, row in map_group.iterrows():
                mods = [row["mods"]] if pd.notna(row.get("mods")) and row["mods"] not in ("NM", "") else []
                conn.execute(
                    "INSERT INTO game_scores "
                    "(match_id, turn, beatmap_id, user_id, username, team_index, "
                    " score, accuracy, max_combo, mods, passed, perfect, rank) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        match_id, turn, int(row["beatmap_id"]),
                        int(row["user_id"]), str(row["username"]), 0,
                        int(row["score"]), float(row["accuracy"]), 0,
                        json.dumps(mods), int(row["passed"]), 0, None,
                    ),
                )

        conn.commit()
        print(f"  seeded mp/{mp_id} → match_id={match_id} ({len(group)} scores)")

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="matches.db")
    args = parser.parse_args()
    print(f"Seeding {args.db} from {CSV.name}…")
    seed(args.db)
    print("Done. Open http://localhost:8080/stats to view.")
