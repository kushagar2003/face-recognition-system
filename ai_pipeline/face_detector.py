"""
Find faces in an image or a camera frame, using OpenCV's YuNet model.

Works the same for files (from image_loader) and live frames (from live_capture).
This module only finds faces. It does not identify anyone.

Heuristic: a detection score is a confidence from the model, not a guarantee.
"""

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from ai_pipeline.config import DEFAULT_CONFIG, PipelineConfig


class ModelLoadError(Exception):
    """The face detection model file is missing or cannot be loaded."""


class FaceDetectionError(Exception):
    """The image cannot be processed for face detection."""


@dataclass(frozen=True)
class DetectedFace:
    x: int
    y: int
    width: int
    height: int
    score: float  # model confidence, 0 to 1. Not a probability of identity.


class FaceDetector:
    """Loads the YuNet model once and reuses it for every image or frame."""

    def __init__(self, cfg: PipelineConfig = DEFAULT_CONFIG) -> None:
        model_path = Path(cfg.yunet_model_path)
        if not model_path.is_file():
            raise ModelLoadError(
                "The face detection model is missing from models\\. "
                "See models\\README.txt for download steps."
            )
        try:
            self._net = cv2.FaceDetectorYN_create(
                str(model_path),
                "",
                (320, 320),
                cfg.detection_score_threshold,
                0.3,   # overlap threshold for removing duplicate boxes
                5000,  # maximum candidate boxes
            )
        except cv2.error:
            raise ModelLoadError(
                "The face detection model could not be loaded. The file may be damaged; "
                "download it again."
            ) from None

    def detect(self, bgr: np.ndarray) -> list[DetectedFace]:
        """
        Return every face found in a BGR image. An empty list means no face.

        Raises:
            FaceDetectionError: If the input is not a 3-channel colour image.
        """
        if not isinstance(bgr, np.ndarray) or bgr.ndim != 3 or bgr.shape[2] != 3:
            raise FaceDetectionError("The image must be a 3-channel colour image.")

        height, width = bgr.shape[:2]
        self._net.setInputSize((width, height))
        _, raw = self._net.detect(bgr)
        if raw is None:
            return []

        faces = []
        for row in raw:
            x, y, w, h = (int(value) for value in row[:4])
            faces.append(DetectedFace(x, y, w, h, float(row[14])))
        return faces
