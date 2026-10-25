"""
Save a captured frame into the project, in a folder for each roll number.

Layout:
    data/captures/<roll_number>/<YYYYmmdd_HHMMSS_micro>.jpg

Only call this for a person who has given consent. Saved photos are biometric
data. The data/captures folder is excluded from Git by .gitignore.
"""

import re
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from ai_pipeline.config import PROJECT_ROOT

CAPTURES_DIR = PROJECT_ROOT / "data" / "captures"

# Letters, digits, '-' and '_' only, up to 32 characters. This blocks path tricks
# such as "../" that could save a file outside the captures folder.
ROLL_NUMBER_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,32}")


class CaptureSaveError(Exception):
    """The frame or roll number is not acceptable, or the file could not be written."""


def save_capture(
    frame: np.ndarray,
    roll_number: str,
    when: datetime | None = None,
    base_dir: Path = CAPTURES_DIR,
    label: str = "",
) -> Path:
    """
    Save a BGR frame as a JPEG and return the file path.

    label is added to the file name, for example "one_face" or "no_face",
    so every capture can be reviewed later. Only letters, digits and '_' are kept.
    """
    if not ROLL_NUMBER_PATTERN.fullmatch(roll_number or ""):
        raise CaptureSaveError(
            "The roll number may only contain letters, digits, '-' and '_' "
            "(up to 32 characters)."
        )
    if not isinstance(frame, np.ndarray) or frame.ndim != 3 or frame.shape[2] != 3:
        raise CaptureSaveError("There is no valid colour image to save.")

    when = when or datetime.now()
    folder = base_dir / roll_number
    folder.mkdir(parents=True, exist_ok=True)
    safe_label = re.sub(r"[^A-Za-z0-9_]", "", label)
    stem = when.strftime("%Y%m%d_%H%M%S_%f") + (f"_{safe_label}" if safe_label else "")
    path = folder / (stem + ".jpg")

    ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok:
        raise CaptureSaveError("The image could not be converted to JPEG.")
    try:
        path.write_bytes(encoded.tobytes())
    except OSError:
        raise CaptureSaveError("The image could not be written. Check the disk and folder permissions.") from None
    return path
