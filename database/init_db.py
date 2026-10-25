"""
Create the database tables. Run from the project root:

    python -m database.init_db            create any missing tables
    python -m database.init_db --status   only show what exists, change nothing

It is safe to run more than once. It never drops or changes existing tables.
All statements run in one transaction, so the database is either fully updated
or left unchanged if something fails.

It prints table names and versions only, never connection details or data.
"""

import sys
from pathlib import Path

from database.config import DatabaseConfigError
from database.db import DatabaseError, get_connection

SCHEMA_FILE = Path(__file__).resolve().parent / "schema.sql"

EXPECTED_TABLES = [
    "schema_migrations",
    "users",
    "persons",
    "face_embeddings",
    "sessions",
    "attendance",
    "audit_logs",
]


def read_schema() -> str:
    return SCHEMA_FILE.read_text(encoding="utf-8")


def existing_tables(conn) -> set[str]:
    rows = conn.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public'"
    ).fetchall()
    return {row[0] for row in rows}


def applied_versions(conn, present: set[str]) -> list[str]:
    if "schema_migrations" not in present:
        return []
    rows = conn.execute(
        "SELECT version FROM schema_migrations ORDER BY version"
    ).fetchall()
    return [row[0] for row in rows]


def show_status(conn) -> None:
    present = existing_tables(conn)
    print("Tables:")
    for name in EXPECTED_TABLES:
        mark = "present" if name in present else "MISSING"
        print(f"  {name:<16} {mark}")
    versions = applied_versions(conn, present)
    print("Applied versions: " + (", ".join(versions) if versions else "none"))


MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def pending_migrations(conn, present: set[str]) -> list[Path]:
    """Migration files, in order, that the database has not applied yet."""
    done = set(applied_versions(conn, present))
    return [
        path for path in sorted(MIGRATIONS_DIR.glob("*.sql"))
        if path.stem not in done
    ]


def apply_schema(conn) -> list[str]:
    """
    Run schema.sql, then any migrations not yet applied.
    Returns the names of tables created by this run.
    """
    before = existing_tables(conn)
    conn.execute(read_schema())  # one statement string; commits with the block

    present = existing_tables(conn)
    for path in pending_migrations(conn, present):
        conn.execute(path.read_text(encoding="utf-8"))

    after = existing_tables(conn)
    return [name for name in EXPECTED_TABLES if name in after and name not in before]


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    status_only = "--status" in argv

    try:
        with get_connection() as conn:
            if status_only:
                show_status(conn)
                return 0

            created = apply_schema(conn)
            present = existing_tables(conn)
    except DatabaseConfigError as exc:
        print(f"FAILED (configuration): {exc}")
        return 1
    except DatabaseError as exc:
        print(f"FAILED (database): {exc}")
        print("Nothing was changed, because the whole update is rolled back on failure.")
        return 1

    if created:
        print("Created: " + ", ".join(created))
    else:
        print("No new tables were needed. The schema is already in place.")

    missing = [name for name in EXPECTED_TABLES if name not in present]
    if missing:
        print("WARNING, still missing: " + ", ".join(missing))
        return 1

    print(f"SUCCESS: all {len(EXPECTED_TABLES)} tables are present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
