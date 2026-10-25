"""
Capture one webcam photo, check it for faces, and optionally save it.

    python -m scripts.live_check                  check only, nothing saved
    python -m scripts.live_check --save 21CS001   save EVERY capture for that roll number

With --save, every capture is kept, whatever the face result. Each one is saved as
    data\\captures\\<roll number>\\<time>_<result>.jpg
and a record (roll number, time, file, result) is written to the database.

Nothing is captured until you press Enter. Use --save only for a person who has
given consent.
"""

import sys
from pathlib import Path

from ai_pipeline.capture_store import ROLL_NUMBER_PATTERN, CaptureSaveError, save_capture
from ai_pipeline.config import PROJECT_ROOT
from ai_pipeline.face_detector import FaceDetectionError, FaceDetector, ModelLoadError
from ai_pipeline.live_capture import CameraError, capture_one_frame


def roll_number_from_args(argv: list[str]) -> str | None:
    if "--save" not in argv:
        return None
    index = argv.index("--save")
    if index + 1 >= len(argv):
        raise SystemExit("Usage: python -m scripts.live_check --save <roll number>")
    return argv[index + 1]


def result_for(face_count: int) -> str:
    if face_count == 0:
        return "no_face"
    if face_count == 1:
        return "one_face"
    return "multiple_faces"


MESSAGES = {
    "no_face": "NO FACE found. The photo is still kept for review.",
    "one_face": "SUCCESS: one face found.",
    "multiple_faces": "Several faces found. The photo is still kept for review.",
}


def record_in_database(roll_number: str, saved: Path, status: str, face_count: int) -> str | None:
    """Write the capture record. Returns None on success, or a reason if it failed."""
    from database.config import DatabaseConfigError
    from database.captures import record_capture
    from database.db import DatabaseError, get_connection

    relative = saved.relative_to(PROJECT_ROOT).as_posix()
    try:
        with get_connection() as conn:
            record_capture(conn, roll_number, relative, face_count, status)
    except DatabaseConfigError as exc:
        return f"configuration: {exc}"
    except DatabaseError as exc:
        return str(exc)
    return None


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    roll_number = roll_number_from_args(argv)

    if roll_number and not ROLL_NUMBER_PATTERN.fullmatch(roll_number):
        print("FAILED: the roll number may only contain letters, digits, '-' and '_' "
              "(up to 32 characters).")
        return 1

    print("This takes ONE photo from your webcam.")
    if roll_number:
        print(f"Every capture is saved for roll number {roll_number}, with or without a face.")
    else:
        print("Nothing is saved (check only).")
    print("Press Enter to take it, or Ctrl+C to cancel.")
    try:
        input()
    except (KeyboardInterrupt, EOFError):
        print("Cancelled. The camera was not used.")
        return 1

    try:
        detector = FaceDetector()
    except ModelLoadError as exc:
        print(f"FAILED (model): {exc}")
        return 1

    try:
        frame = capture_one_frame()
    except CameraError as exc:
        print(f"FAILED (camera): {exc}")
        return 1

    try:
        faces = detector.detect(frame)
    except FaceDetectionError as exc:
        print(f"FAILED (image): {exc}")
        return 1

    status = result_for(len(faces))
    print(MESSAGES[status])
    if status == "one_face":
        face = faces[0]
        print(f"  face size {face.width}x{face.height} pixels, confidence {face.score:.2f}")
    if status == "no_face":
        print("  Tip: face the camera, improve the light, and try again.")

    if not roll_number:
        return 0 if status == "one_face" else 1

    try:
        saved = save_capture(frame, roll_number, label=status)
    except CaptureSaveError as exc:
        print(f"FAILED (save): {exc}")
        return 1
    print(f"Photo saved: {saved.relative_to(PROJECT_ROOT).as_posix()}")

    problem = record_in_database(roll_number, saved, status, len(faces))
    if problem:
        print("WARNING: the photo was saved, but the database record was NOT written.")
        print(f"  reason: {problem}")
        return 1
    print("Database record written (roll number, time, file, result).")
    return 0 if status == "one_face" else 1


if __name__ == "__main__":
    sys.exit(main())
