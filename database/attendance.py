"""
Login and logout rules for attendance.

Each function takes an open database connection. The caller uses get_connection(),
which commits when the block finishes without error, and rolls back otherwise.

Every decision is made by the database and this module, never by the camera or
the browser. A recognised face is only an input; these rules decide what is saved.

Results are returned as short codes, so the caller can show a clear message:
    login_recorded        logged in now
    already_logged_in     this person already logged in to this session
    logout_recorded       logged out now; the duration is returned
    already_logged_out    this person has already logged out of this session
    no_login              logout was tried before any login
    unknown_person        no such person
    inactive_person       the person is not active, so they cannot check in
    unknown_session       no such session
    session_closed        the session has been closed
"""

from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True)
class AttendanceResult:
    code: str
    person_id: int
    session_id: int
    duration: timedelta | None = None


def _check_eligibility(conn, person_id: int, session_id: int) -> str | None:
    """Return a refusal code if this person or session cannot be used, else None."""
    person = conn.execute(
        "SELECT status FROM persons WHERE id = %s", (person_id,)
    ).fetchall()
    if not person:
        return "unknown_person"
    if person[0][0] != "active":
        return "inactive_person"

    session = conn.execute(
        "SELECT is_open FROM sessions WHERE id = %s", (session_id,)
    ).fetchall()
    if not session:
        return "unknown_session"
    if not session[0][0]:
        return "session_closed"
    return None


def record_login(conn, person_id: int, session_id: int) -> AttendanceResult:
    """Record a login. It can happen only once per person per session."""
    refusal = _check_eligibility(conn, person_id, session_id)
    if refusal:
        return AttendanceResult(refusal, person_id, session_id)

    # The unique constraint on (person_id, session_id) blocks a second login even
    # if two scans happen at the same moment. DO NOTHING means "already there".
    inserted = conn.execute(
        """
        INSERT INTO attendance (person_id, session_id, check_in_at)
        VALUES (%s, %s, now())
        ON CONFLICT (person_id, session_id) DO NOTHING
        RETURNING id
        """,
        (person_id, session_id),
    ).fetchall()
    if inserted:
        return AttendanceResult("login_recorded", person_id, session_id)
    return AttendanceResult("already_logged_in", person_id, session_id)


def record_logout(conn, person_id: int, session_id: int) -> AttendanceResult:
    """Record a logout for a login that is still open."""
    refusal = _check_eligibility(conn, person_id, session_id)
    if refusal:
        return AttendanceResult(refusal, person_id, session_id)

    # Only an open login (logout_at IS NULL) can be closed, so a second logout
    # matches nothing and is refused.
    closed = conn.execute(
        """
        UPDATE attendance
           SET logout_at = now()
         WHERE person_id = %s
           AND session_id = %s
           AND logout_at IS NULL
        RETURNING duration
        """,
        (person_id, session_id),
    ).fetchall()
    if closed:
        duration = closed[0][0]
        return AttendanceResult("logout_recorded", person_id, session_id, duration)

    # Nothing was closed. Work out why, so the message is clear.
    any_row = conn.execute(
        "SELECT logout_at FROM attendance WHERE person_id = %s AND session_id = %s",
        (person_id, session_id),
    ).fetchall()
    if not any_row:
        return AttendanceResult("no_login", person_id, session_id)
    return AttendanceResult("already_logged_out", person_id, session_id)
