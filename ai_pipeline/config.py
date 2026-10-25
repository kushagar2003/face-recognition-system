"""
Central configuration for the AI/ML pipeline.

All thresholds here are starting points, not validated values.
Tune them on your own labelled test data (see the evaluation script, later).
"""

from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"


@dataclass(frozen=True)
class PipelineConfig:
    # --- Model files (OpenCV Zoo, see README for license checks) ---
    yunet_model_path: Path = MODELS_DIR / "face_detection_yunet_2023mar.onnx"
    sface_model_path: Path = MODELS_DIR / "face_recognition_sface_2021dec.onnx"

    # --- Image loading rules ---
    allowed_extensions: tuple[str, ...] = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
    max_file_size_mb: float = 10.0
    min_image_width: int = 160
    min_image_height: int = 160
    max_image_dimension: int = 6000

    # --- Detection and quality (heuristic starting values) ---
    detection_score_threshold: float = 0.9
    min_face_size_px: int = 80
    blur_variance_threshold: float = 100.0   # Laplacian variance; below this = likely blurry
    min_brightness: float = 40.0             # mean grey level, 0-255
    max_brightness: float = 215.0

    # --- Matching (SFace default cosine threshold from OpenCV samples; validate before use) ---
    cosine_match_threshold: float = 0.363


DEFAULT_CONFIG = PipelineConfig()
