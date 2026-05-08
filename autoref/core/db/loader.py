from functools import cache
from pathlib import Path

_QUERIES_DIR = Path(__file__).parent / "queries"


@cache
def sql(path: str) -> str:
    """Load a .sql file from queries/.

    path uses dot notation: "matches.history" → queries/matches/history.sql
    Single-segment paths load from queries/ root: "foo" → queries/foo.sql
    """
    pkg, _, name = path.rpartition(".")
    if pkg:
        return (_QUERIES_DIR / pkg / f"{name}.sql").read_text()
    return (_QUERIES_DIR / f"{name}.sql").read_text()
