"""
One capture for the web app: webcam -> face check -> save photo -> database record.

These are the same steps as scripts/live_check.py, but the results are returned
as data instead of printed. Only one capture runs at a time.

Only call this for a person who has given consent.
"""

import threading
from datetime import datetime

from ai_pipeline.capture_store import CaptureSaveError, save_capture
from ai_pipeline.config import PROJECT_ROOT
from ai_pipeline.face_detector import FaceDetectionError, FaceDetector, ModelLoadError
from ai_pipeline.live_capture import CameraError, capture_one_frame
from database.captures import list_captures, record_capture
from database.config import DatabaseConfigError
from database.db import DatabaseError, get_connection

MESSAGES = {
    "no_face": "NO FACE found. The photo is still kept for review.",
    "one_face": "SUCCESS: one face found.",
    "multiple_faces": "Several faces found. The photo is still kept for review.",
}

DATABASE_NOT_CONFIGURED = "Database is not configured. Check the .env file."


class CaptureServiceError(Exception):
    """An error the web API returns to the browser as JSON."""

    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


_capture_lock = threading.Lock()
_detector_lock = threading.Lock()
_detector: FaceDetector | None = None


def _get_detector() -> FaceDetector:
    """Load the face detector once and reuse it."""
    global _detector
    with _detector_lock:
        if _detector is None:
            try:
                _detector = FaceDetector()
            except ModelLoadError as exc:
                raise CaptureServiceError(503, "model_missing", str(exc)) from None
        return _detector


def _result_for(face_count: int) -> str:
    if face_count == 0:
        return "no_face"
    if face_count == 1:
        return "one_face"
    return "multiple_faces"


def _save_record(roll_number: str, image_path: str, face_count: int,
                 status: str, when: datetime) -> tuple[bool, str | None]:
    """Write the database record. The photo is already saved, so a failure here is reported, not raised."""
    try:
        with get_connection() as conn:
            record_capture(conn, roll_number, image_path, face_count, status, captured_at=when)
        return True, None
    except DatabaseConfigError:
        return False, DATABASE_NOT_CONFIGURED
    except DatabaseError as exc:
        return False, str(exc)


def run_capture(roll_number: str) -> dict:
    """Take one photo, check it, save it, and record it. Returns a dict for the JSON response."""
    if not _capture_lock.acquire(blocking=False):
        raise CaptureServiceError(409, "busy", "Another capture is in progress. Wait a moment and try again.")
    try:
        detector = _get_detector()

        try:
            frame = capture_one_frame()
        except CameraError as exc:
            raise CaptureServiceError(503, "camera", str(exc)) from None
        when = datetime.now().astimezone()

        try:
            faces = detector.detect(frame)
        except FaceDetectionError as exc:
            raise CaptureServiceError(500, "image", str(exc)) from None

        status = _result_for(len(faces))
        try:
            saved = save_capture(frame, roll_number, when=when, label=status)
        except CaptureSaveError as exc:
            raise CaptureServiceError(500, "save", str(exc)) from None

        image_path = saved.relative_to(PROJECT_ROOT).as_posix()
        db_saved, db_message = _save_record(roll_number, image_path, len(faces), status, when)

        face = None
        if status == "one_face":
            face = {
                "width": faces[0].width,
                "height": faces[0].height,
                "confidence": round(float(faces[0].score), 2),
            }

        return {
            "roll_number": roll_number,
            "status": status,
            "face_count": len(faces),
            "face": face,
            "message": MESSAGES[status],
            "captured_at": when.isoformat(timespec="seconds"),
            "image_path": image_path,
            "database_saved": db_saved,
            "database_message": db_message,
        }
    finally:
        _capture_lock.release()


def fetch_captures(roll_number: str | None, limit: int) -> list[dict]:
    """Return the newest capture records. No image bytes are returned."""
    try:
        with get_connection() as conn:
            return list_captures(conn, roll_number, limit)
    except DatabaseConfigError:
        raise CaptureServiceError(503, "database_not_configured", DATABASE_NOT_CONFIGURED) from None
    except DatabaseError as exc:
        raise CaptureServiceError(503, "database_unavailable", str(exc)) from None


def check_database() -> None:
    """Run SELECT 1. Raises CaptureServiceError if the database cannot be reached."""
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
    except DatabaseConfigError:
        raise CaptureServiceError(503, "database_not_configured", DATABASE_NOT_CONFIGURED) from None
    except DatabaseError as exc:
        raise CaptureServiceError(503, "database_unavailable", str(exc)) from None
