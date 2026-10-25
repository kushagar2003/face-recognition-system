"""
Take one frame from the webcam, only when the operator asks for it.

Privacy rules this module follows:
  * It captures one frame per call and releases the camera straight after.
  * It never runs in the background and never records video.
  * It never saves the frame to disk. The frame lives in memory only.
"""

import os

import cv2
import numpy as np


class CameraError(Exception):
    """The webcam cannot be opened or returned no image."""


def capture_one_frame(camera_index: int = 0, warmup_frames: int = 15) -> np.ndarray:
    """
    Return one BGR frame from the webcam.

    The first frames are discarded while the camera adjusts exposure and focus.
    """
    backend = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY  # faster start on Windows
    camera = cv2.VideoCapture(camera_index, backend)
    try:
        if not camera.isOpened():
            raise CameraError(
                "The webcam could not be opened. Check that it is connected and that "
                "no other app (such as Teams or Zoom) is using it."
            )
        frame = None
        for _ in range(warmup_frames):
            ok, current = camera.read()
            if ok:
                frame = current
        if frame is None:
            raise CameraError("The webcam opened but returned no image. Try again.")
        return frame
    finally:
        camera.release()
