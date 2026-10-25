"""
Setup check: tells you what is wrong and how to fix it. Run from the project root:

    python -m scripts.doctor

It checks, in order:
  1. Python version (3.11 or 3.12)
  2. Virtual environment is active (.venv)
  3. Required packages are installed
  4. Model files are present (needed later for face detection)
  5. .env exists and DATABASE_URL is set correctly
  6. The Neon database answers SELECT 1

It never prints DATABASE_URL, the password, or any image data.
Exit code 0 means every required check passed.
"""

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = PROJECT_ROOT / ".venv"
REQUIRED_PACKAGES = [
    ("cv2", "opencv-python==4.10.0.84"),
    ("numpy", "numpy<2.0"),
    ("PIL", "pillow==11.3.0"),
    ("psycopg", "psycopg[binary]==3.2.3"),
    ("dotenv", "python-dotenv==1.0.1"),
]
MODEL_FILES = [
    "face_detection_yunet_2023mar.onnx",
    "face_recognition_sface_2021dec.onnx",
]

failures = 0


def report(name: str, ok: bool, fix: str = "") -> None:
    global failures
    print(f"[ OK ] {name}" if ok else f"[FAIL] {name}")
    if not ok:
        failures += 1
        if fix:
            print(f"       fix: {fix}")


SUPPORTED_PYTHON = ((3, 11), (3, 12))


def check_python() -> None:
    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    report(
        f"Python version is {version} (supported: 3.11 and 3.12, 64-bit)",
        sys.version_info[:2] in SUPPORTED_PYTHON and sys.maxsize > 2**32,
        "Run: py -0  then recreate the environment with: py -3.12 -m venv .venv "
        "(or py -3.11). Install 64-bit Python if needed.",
    )


def check_venv() -> None:
    active = Path(sys.prefix).resolve() == VENV_DIR.resolve()
    if not VENV_DIR.exists():
        report(".venv folder exists", False,
               "Run: py -3.12 -m venv .venv  (from the project root)")
        return
    report(
        "Virtual environment is active",
        active,
        "Run: .\\.venv\\Scripts\\Activate.ps1  (you should see (.venv) in the prompt)",
    )


def check_packages() -> None:
    missing = [pkg for module, pkg in REQUIRED_PACKAGES
               if importlib.util.find_spec(module) is None]
    report(
        "Required packages are installed",
        not missing,
        "Run: python -m pip install -r requirements.txt  (missing: "
        + ", ".join(missing) + ")" if missing else "",
    )


def check_models() -> None:
    models_dir = PROJECT_ROOT / "models"
    missing = [name for name in MODEL_FILES if not (models_dir / name).is_file()]
    report(
        "Model files are in models\\ (needed for face detection, a later step)",
        not missing,
        "See models\\README.txt for download steps. Missing: " + ", ".join(missing)
        if missing else "",
    )


def check_env_and_database() -> None:
    env_file = PROJECT_ROOT / ".env"
    report(
        ".env file exists",
        env_file.is_file(),
        "Run: python -m scripts.set_env",
    )
    if not env_file.is_file():
        return

    # Count the DATABASE_URL lines. Two of them is a common leftover after hand
    # editing. The LAST line wins, so a template line below a correct one
    # silently replaces it. Only the count is read here, never the values.
    lines = env_file.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    url_lines = [ln for ln in lines if ln.strip().upper().startswith("DATABASE_URL=")]
    if len(url_lines) > 1:
        report(
            ".env has exactly one DATABASE_URL line",
            False,
            f"Found {len(url_lines)} DATABASE_URL lines. The last one is used, so an "
            "older line below a correct one silently replaces it. Keep exactly one. "
            "Run: python -m scripts.set_env",
        )

    try:
        from database.config import DatabaseConfigError, load_database_url
    except ImportError as exc:
        report("Database config module loads", False,
               f"Install packages first (python -m pip install -r requirements.txt). {exc.name}")
        return

    try:
        load_database_url()
        report("DATABASE_URL is set and valid", True)
    except DatabaseConfigError as exc:
        report("DATABASE_URL is set and valid", False, str(exc))
        return

    try:
        import psycopg
    except ImportError as exc:
        report("Database driver loads", False,
               f"Install packages first (python -m pip install -r requirements.txt). {exc.name}")
        return

    url = load_database_url()
    try:
        with psycopg.connect(url, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        report("Neon database answers SELECT 1", True)
    except psycopg.Error as exc:
        # Print only a safe category. The raw message can contain the host or user.
        report("Neon database answers SELECT 1", False,
               f"{explain_connection_error(exc)}\n       database said (your details hidden): "
               f"{redact_error(exc, url)}\n       (error type: {type(exc).__name__})")


def redact_error(exc: Exception, url: str) -> str:
    """
    Return the driver's message with the user name, password, host and database
    replaced by placeholders, so the real cause can be shown safely.
    """
    from urllib.parse import quote, unquote, urlsplit

    message = str(exc)
    parts = urlsplit(url)
    replacements = []
    if parts.password:
        replacements += [(parts.password, "<password>"),
                         (unquote(parts.password), "<password>"),
                         (quote(unquote(parts.password), safe=""), "<password>")]
    if parts.username:
        replacements.append((parts.username, "<user>"))
    if parts.hostname:
        replacements.append((parts.hostname, "<host>"))
    path_db = parts.path.strip("/")
    if path_db:
        replacements.append((path_db, "<database>"))
    # Replace the longest values first, so a short value cannot break a longer one.
    for value, label in sorted(replacements, key=lambda item: -len(item[0])):
        if value:
            message = message.replace(value, label)
    # Keep only the first few lines; libpq messages are short.
    return " | ".join(line.strip() for line in message.splitlines() if line.strip())[:400]


def explain_connection_error(exc: Exception) -> str:
    """Map a driver error to a fix. Never returns the raw message (it can hold secrets)."""
    text = str(exc).lower()
    if "password authentication failed" in text:
        return ("Password was rejected. Copy the connection string again from Neon, and "
                "URL-encode special characters in the password (Step 2 table).")
    if ("could not translate host name" in text or "name or service not known" in text
            or "getaddrinfo" in text or "nodename nor servname" in text):
        return ("Host name not found. Check the host part of DATABASE_URL, your internet "
                "connection, and any VPN or DNS filter.")
    if "does not exist" in text and "database" in text:
        return ("Database name is wrong. It is the part after the last slash in "
                "DATABASE_URL.")
    if "ssl" in text:
        return ("SSL handshake failed. Keep sslmode=require, and check that antivirus or a "
                "firewall is not inspecting HTTPS traffic.")
    if "timeout" in text or "timed out" in text:
        return ("Connection timed out. Check your internet, firewall, or VPN, then try again.")
    if "endpoint id" in text or "endpoint=" in text:
        return ("Neon needs the endpoint ID for this connection. Copy the full connection "
                "string from Neon's Connect box rather than building it by hand.")
    if "server closed the connection" in text or "connection refused" in text \
            or "could not connect to server" in text:
        return ("The server refused or dropped the connection. Check the host name is "
                "copied exactly, including any '-pooler' part, and that no firewall or VPN "
                "is blocking it.")
    if "invalid channel_binding" in text:
        return ("A value in the connection string is cut off. The setup scripts now drop "
                "it automatically. If this still shows, run python -m scripts.set_env again.")
    if "channel binding" in text or "scram" in text:
        return ("Login handshake failed (SCRAM or channel binding). Copy the connection "
                "string from Neon again so its settings match.")
    if "no pg_hba.conf entry" in text:
        return ("Neon rejected this client setting. Copy the connection string from Neon "
                "again and keep sslmode=require.")
    if "endpoint" in text or "disabled" in text or "suspended" in text:
        return ("The Neon endpoint may be suspended or disabled. Open the Neon dashboard and "
                "check the project.")
    return ("Connection failed for a reason not in the list. The redacted message below "
            "shows the cause; see the Step 2 troubleshooting table.")


def main() -> int:
    print(f"Project folder: {PROJECT_ROOT}\n")
    check_python()
    check_venv()
    check_packages()
    check_models()
    check_env_and_database()
    print()
    if failures == 0:
        print("All required checks passed.")
        return 0
    print(f"{failures} check(s) failed. Fix the items above, then run this again.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
