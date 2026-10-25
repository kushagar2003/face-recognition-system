"""
Manage PostgreSQL connections with psycopg 3.

Pattern used everywhere:
    with get_connection() as conn:
        ...run SQL...
    # On success the transaction commits and the connection closes.
    # On an exception it rolls back and the connection closes.

Connections are opened per unit of work and closed right after. Nothing is
kept open between requests.
"""

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg

from database.config import load_database_url


class DatabaseError(Exception):
    """Raised for connection or query failures. Messages contain no secrets."""


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    """
    Open a connection, yield it, then commit or roll back and close it.

    Raises:
        DatabaseConfigError: From config, if DATABASE_URL is missing or unsafe.
        DatabaseError: If the server cannot be reached or a statement fails.
    """
    url = load_database_url()  # raises DatabaseConfigError on bad config

    try:
        # psycopg 3: leaving the 'with' block commits on success, rolls back
        # on an exception, and closes the connection.
        with psycopg.connect(url, connect_timeout=10) as conn:
            yield conn
    except psycopg.OperationalError:
        # Covers unreachable host, bad password, SSL failures, and a connection
        # lost during a request. The original message is dropped because it can
        # include host details.
        raise DatabaseError(
            "Database connection failed or was lost. Check your internet "
            "connection, DATABASE_URL, and that the Neon project is active."
        ) from None
    except psycopg.Error as exc:
        raise DatabaseError(
            f"Database error ({type(exc).__name__}). The transaction was rolled back."
        ) from None
