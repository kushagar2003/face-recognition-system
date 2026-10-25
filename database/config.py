"""
Load the database connection string from the local .env file.

Secrets are never printed. Error messages name the variable, never its value.
"""

import os
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

# SSL modes that encrypt the connection. Neon requires encrypted connections.
ALLOWED_SSL_MODES = {"require", "verify-ca", "verify-full"}

# Values the driver accepts for channel_binding.
VALID_CHANNEL_BINDING = ("disable", "prefer", "require")


class DatabaseConfigError(Exception):
    """Raised when the database configuration is missing or unsafe."""


def load_database_url() -> str:
    """
    Read DATABASE_URL from the environment or the local .env file.

    Returns:
        A PostgreSQL connection string that requires SSL.

    Raises:
        DatabaseConfigError: If DATABASE_URL is missing, not a PostgreSQL URL,
            or configured without encryption.
    """
    # Values already set in the environment win over the .env file.
    # utf-8-sig also handles files Notepad saved with a byte-order mark.
    load_dotenv(dotenv_path=ENV_FILE, override=False, encoding="utf-8-sig")

    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise DatabaseConfigError(
            "DATABASE_URL is not set. Create a .env file in the project root "
            "(copy .env.example) and paste your Neon connection string."
        )

    parts = urlsplit(url)
    if parts.scheme not in ("postgresql", "postgres"):
        raise DatabaseConfigError(
            "DATABASE_URL must start with 'postgresql://'. Check for typos or a "
            "missing value."
        )
    # Catch the placeholder words from .env.example, such as YOUR_HOST, USER,
    # ENCODED_PASSWORD, HOST, and DATABASE.
    if re.search(r"YOUR_|\bENCODED_PASSWORD\b|\bUSER:|@HOST\b|/DATABASE\b", url):
        raise DatabaseConfigError(
            "DATABASE_URL still contains a placeholder. Replace it with your real "
            "Neon connection string."
        )

    # Make sure SSL is required. If sslmode is missing, add sslmode=require.
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    ssl_mode = query.get("sslmode")
    if ssl_mode is None:
        query["sslmode"] = "require"
    elif ssl_mode not in ALLOWED_SSL_MODES:
        raise DatabaseConfigError(
            "DATABASE_URL disables encryption (sslmode). Use sslmode=require, "
            "verify-ca, or verify-full."
        )

    # channel_binding is optional. A value cut off during a paste (for example
    # "requir") makes the driver refuse to connect. Drop any invalid value and
    # let the driver use its default. Encryption is still required by sslmode.
    if query.get("channel_binding") not in (None, *VALID_CHANNEL_BINDING):
        del query["channel_binding"]

    return urlunsplit(parts._replace(query=urlencode(query)))
