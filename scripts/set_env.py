"""
Write the .env file from your Neon connection string, without using Notepad.

Run from the project root, with the virtual environment active:

    python -m scripts.set_env

It asks you to paste the Neon connection string. The input is hidden, so the
string is not echoed to the screen and is not saved in PowerShell history.

If you cannot tell whether the paste worked, run it in visible mode instead:

    python -m scripts.set_env --show

In visible mode the string appears on screen, so do not use it if someone can
see your screen. It is still kept out of PowerShell history either way.

It then cleans the string, checks it, writes .env, and tests the connection.
The connection string and password are never printed.
"""

import getpass
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

HEADER = """# Local settings. Never commit this file to Git.
# Written by: python -m scripts.set_env
#
# DATABASE_URL is your Neon PostgreSQL connection string.
# If the password contains special characters (@ : / ? # % &), they must be
# percent-encoded, for example @ becomes %40.
"""

PLACEHOLDER_WORDS = (
    "YOUR_", "ENCODED_PASSWORD", "USER:", "@HOST", "/DATABASE",
)
# Characters that must be percent-encoded inside a password.
NEEDS_ENCODING = set("@/?#[] ")


def clean(raw: str) -> str:
    """Remove the wrapping that a copied connection string often carries."""
    text = raw.strip()
    if text.lower().startswith("psql "):    # Neon can show a full psql command
        text = text[5:].strip()
    text = text.strip("'\"").strip()        # surrounding quotes
    if text.upper().startswith("DATABASE_URL="):
        text = text.split("=", 1)[1].strip().strip("'\"")
    # A connection string never contains whitespace: a real space in a password
    # is percent-encoded as %20. Removing it repairs a paste that wrapped across
    # lines, which would otherwise leave a break in the middle of the host name.
    return "".join(text.split())


def safe_description(text: str) -> str:
    """
    Describe what was entered without revealing it.

    Only the scheme (the part before ://) is shown. Credentials always come
    after ://, so they can never appear here.
    """
    count = len(text)
    if "://" in text:
        scheme = text.split("://", 1)[0]
        return f"received {count} characters beginning with '{scheme}://'"
    detail = f"received {count} characters with no '://' in them"
    if ".neon.tech" in text:
        detail += " (it does contain '.neon.tech', so the 'postgresql://' start is missing)"
    return detail


def describe_problem(url: str) -> str | None:
    """Return a human-readable problem with the URL, or None if it looks usable."""
    if not url:
        return "Nothing was entered."
    for word in PLACEHOLDER_WORDS:
        if word in url:
            return (f"The string still contains the template text '{word}'. "
                    "Copy the real string from the Neon dashboard (Connect button).")
    try:
        parts = urlsplit(url)
    except ValueError:
        return "The string is not a valid URL. Copy it again from Neon."
    if parts.scheme not in ("postgresql", "postgres"):
        return "The string must start with 'postgresql://'."
    if not parts.hostname:
        return "No host found. The host looks like ep-xxxx.region.aws.neon.tech."
    if not parts.username:
        return "No user name found. It is the part between // and the colon."
    if not parts.path.strip("/"):
        return "No database name found. It is the part after the host."
    return None


def normalise(url: str) -> tuple[str, str, str]:
    """Return (final_url, host, database) with sslmode=require guaranteed."""
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    if query.get("sslmode") not in ("require", "verify-ca", "verify-full"):
        query["sslmode"] = "require"
    # Drop a channel_binding value cut off during a paste (for example "requir").
    if query.get("channel_binding") not in (None, "disable", "prefer", "require"):
        del query["channel_binding"]
    final = urlunsplit(parts._replace(query=urlencode(query)))
    return final, parts.hostname or "", parts.path.strip("/")


def warn_about_password(url: str) -> None:
    password = urlsplit(url).password or ""
    if "%" in password:
        return  # already percent-encoded
    bad = sorted(NEEDS_ENCODING & set(password))
    if bad:
        print(f"  Note: the password contains {' '.join(bad)} , which normally needs")
        print("  percent-encoding. If the connection is refused, encode it and run again.")


def test_connection() -> bool:
    try:
        import psycopg
    except ImportError:
        print("  Could not test the connection: psycopg is not installed.")
        print("  Run: python -m pip install -r requirements.txt")
        return False

    from database.config import load_database_url

    try:
        with psycopg.connect(load_database_url(), connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return True
    except psycopg.Error as exc:
        from scripts.doctor import explain_connection_error, redact_error
        url = load_database_url()
        print(f"  {explain_connection_error(exc)}")
        print(f"  Database said (your details hidden): {redact_error(exc, url)}")
        print(f"  (error type: {type(exc).__name__})")
        return False


def prompt_parts() -> str | None:
    """
    Ask for each piece of the connection separately and build the string.

    The password is encoded automatically, so special characters are safe.
    Nothing is printed except prompts.
    """
    from urllib.parse import quote

    print("Enter each part from the Neon dashboard (Connect button).")
    print("The password is hidden. Press Enter on an empty line to cancel.\n")
    try:
        host = input("Host (looks like ep-xxxx.region.aws.neon.tech): ").strip()
        user = input("User name (for example neondb_owner): ").strip()
        password = getpass.getpass("Password (hidden): ")
        database = input("Database name [press Enter for neondb]: ").strip() or "neondb"
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled. Nothing was changed.")
        return None

    if not host or not user or not password:
        print("\nNot saved: the host, user name and password are all required.")
        return None

    return (f"postgresql://{quote(user, safe='')}:{quote(password, safe='')}"
            f"@{host}/{database}?sslmode=require")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    show_input = "--show" in argv

    print("Paste your Neon connection string, then press Enter.")
    print("Get it from the Neon dashboard using the Connect button.")
    print("It starts with postgresql:// and is one long line.\n")
    if show_input:
        print("Visible mode: the string WILL appear on screen as you paste.\n")
    else:
        print("Nothing appears on screen while you paste. That is normal.")
        print("If you cannot tell whether the paste worked, cancel with Enter and")
        print("run it again as:  python -m scripts.set_env --show\n")

    if "--parts" in argv:
        url = prompt_parts()
        if url is None:
            return 1
    else:
        try:
            raw = input("Connection string: ") if show_input else getpass.getpass("Connection string: ")
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled. Nothing was changed.")
            return 1
        url = clean(raw)
    problem = describe_problem(url)
    if problem:
        print(f"\nNot saved: {problem}")
        if url:
            print(f"What the script got: {safe_description(url)}.")
            print("Only the part before :// is shown here; your password is never displayed.")
        print("\nTo see exactly what you are pasting, run:")
        print("  python -m scripts.set_env --show")
        return 1

    final_url, host, database = normalise(url)

    if ENV_FILE.exists():
        answer = input(f"\n.env already exists. Overwrite it? [y/N]: ").strip().lower()
        if answer not in ("y", "yes"):
            print("Cancelled. Nothing was changed.")
            return 1

    ENV_FILE.write_text(f"{HEADER}\nDATABASE_URL={final_url}\n", encoding="utf-8")

    print(f"\nSaved .env")
    print(f"  host:     {host}")
    print(f"  database: {database}")
    print("  password: hidden")
    warn_about_password(final_url)

    print("\nTesting the connection...")
    if test_connection():
        print("  SUCCESS: the database answered.")
        print("\nNow run: python -m scripts.doctor")
        return 0

    print("\nThe file was saved, but the database did not answer.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
