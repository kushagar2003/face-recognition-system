"""
Connection test: confirms the Neon database is reachable.

Run from the project root:
    python -m database.check_connection

It prints only success or failure. It never prints DATABASE_URL or the password.
"""

import sys

from database.config import DatabaseConfigError
from database.db import DatabaseError, get_connection


def main() -> int:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                (value,) = cur.fetchone()
        if value != 1:
            print("FAILED: unexpected response from the database.")
            return 1
    except DatabaseConfigError as exc:
        print(f"FAILED (configuration): {exc}")
        return 1
    except DatabaseError as exc:
        print(f"FAILED (connection): {exc}")
        return 1

    print("SUCCESS: connected to Neon PostgreSQL and ran SELECT 1.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
