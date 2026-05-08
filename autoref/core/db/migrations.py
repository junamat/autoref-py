from __future__ import annotations

import sqlite3
from pathlib import Path

_SCHEMA_DIR = Path(__file__).parent / "schema"


def _run_file(conn: sqlite3.Connection, path: Path) -> None:
    """Execute each statement in a .sql file, tolerating duplicate-column errors."""
    for stmt in path.read_text().split(";"):
        stmt = stmt.strip()
        if not stmt or stmt.startswith("--"):
            continue
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError as exc:
            if "duplicate column" in str(exc).lower():
                pass
            else:
                raise
    conn.commit()


def run_migrations(conn: sqlite3.Connection) -> None:
    """Apply all pending schema migrations in version order."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version    INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}

    for sql_file in sorted(_SCHEMA_DIR.glob("*.sql")):
        version = int(sql_file.stem.split("_")[0])
        if version in applied:
            continue
        _run_file(conn, sql_file)
        conn.execute("INSERT INTO schema_migrations(version) VALUES (?)", (version,))
        conn.commit()
