from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def connect(path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection with project-standard pragmas."""
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    _p = Path(str(path))
    if _p.exists():
        os.chmod(_p, 0o600)
    return conn
