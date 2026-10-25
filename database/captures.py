"""
Store one record per live capture: roll number, time, image path, and face result.

Takes an open connection. The caller uses get_connection(), which commits on
success and rolls back on error.
"""

from datetime import datetime

ALLOWED_STATUS = ("one_face", "no_face", "multiple_faces")


def record_capture(
    conn,
    roll_number: str,
    image_path: str,
    face_count: int,
    status: str,
    captured_at: datetime | None = None,
) -> int:
    """Insert a capture record and return its id."""
    if status not in ALLOWED_STATUS:
        raise ValueError(f"status must be one of {ALLOWED_STATUS}")
    row = conn.execute(
        """
        INSERT INTO captures (roll_number, captured_at, image_path, face_count, status)
        VALUES (%s, COALESCE(%s, now()), %s, %s, %s)
        RETURNING id
        """,
        (roll_number, captured_at, image_path, face_count, status),
    ).fetchall()
    return int(row[0][0])


def list_captures(conn, roll_number: str | None = None, limit: int = 50) -> list[dict]:
    """Return the newest capture records, optionally for one roll number. No image bytes."""
    limit = max(1, min(int(limit), 200))
    sql = "SELECT id, roll_number, captured_at, face_count, status, image_path FROM captures"
    params: tuple = ()
    if roll_number:
        sql += " WHERE roll_number = %s"
        params = (roll_number,)
    sql += " ORDER BY captured_at DESC, id DESC LIMIT %s"
    params += (limit,)
    rows = conn.execute(sql, params).fetchall()
    return [
        {
            "id": int(row[0]),
            "roll_number": row[1],
            "captured_at": row[2].isoformat(),
            "face_count": int(row[3]),
            "status": row[4],
            "image_path": row[5],
        }
        for row in rows
    ]
