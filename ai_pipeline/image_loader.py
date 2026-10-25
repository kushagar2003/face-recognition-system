"""
Load and validate a local image file.

Returns a BGR image (OpenCV's default colour order) as a NumPy array.
Error messages never include image contents.
"""

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from ai_pipeline.config import DEFAULT_CONFIG, PipelineConfig


class ImageLoadError(Exception):
    """Raised when an image cannot be loaded or fails basic validation."""


def load_image(path: str | Path, cfg: PipelineConfig = DEFAULT_CONFIG) -> np.ndarray:
    """
    Load an image from a local file and validate it.

    Args:
        path: Path to the image file.
        cfg: Pipeline configuration with the loading rules.

    Returns:
        A 3-channel BGR image as a uint8 NumPy array with shape (height, width, 3).

    Raises:
        ImageLoadError: If the file is missing, unsupported, too large, empty,
            corrupted, or smaller/larger than the configured limits.
    """
    file_path = Path(path)

    # 1. The file must exist and be a regular file.
    if not file_path.is_file():
        raise ImageLoadError("Image file does not exist or is not a regular file.")

    # 2. The extension must be an allowed image type.
    if file_path.suffix.lower() not in cfg.allowed_extensions:
        allowed = ", ".join(cfg.allowed_extensions)
        raise ImageLoadError(f"Unsupported image type. Allowed types: {allowed}.")

    # 3. The file must not be empty or too large.
    size_mb = file_path.stat().st_size / (1024 * 1024)
    if size_mb == 0:
        raise ImageLoadError("Image file is empty.")
    if size_mb > cfg.max_file_size_mb:
        raise ImageLoadError(
            f"Image file is {size_mb:.1f} MB; the limit is {cfg.max_file_size_mb} MB."
        )

    # 4. Read only the image header to get its size, BEFORE full decoding.
    #    A small file can decode to a huge image, so this stops oversized
    #    images before they use lots of memory.
    try:
        with Image.open(file_path) as probe:
            probe_width, probe_height = probe.size
    except (OSError, ValueError):
        raise ImageLoadError("Image could not be decoded. The file may be corrupted.") from None
    if probe_width > cfg.max_image_dimension or probe_height > cfg.max_image_dimension:
        raise ImageLoadError(
            f"Image is {probe_width}x{probe_height} pixels; the maximum dimension is "
            f"{cfg.max_image_dimension}."
        )

    # 5. Read the raw bytes, then decode. np.fromfile + imdecode handles
    #    non-ASCII Windows paths, which cv2.imread can fail on.
    raw_bytes = np.fromfile(str(file_path), dtype=np.uint8)
    image = cv2.imdecode(raw_bytes, cv2.IMREAD_COLOR)  # always returns 3 channels
    if image is None:
        raise ImageLoadError("Image could not be decoded. The file may be corrupted.")

    # 6. Check final dimensions (minimum size and a second maximum check).
    height, width = image.shape[:2]
    if width < cfg.min_image_width or height < cfg.min_image_height:
        raise ImageLoadError(
            f"Image is {width}x{height} pixels; the minimum is "
            f"{cfg.min_image_width}x{cfg.min_image_height}."
        )
    if width > cfg.max_image_dimension or height > cfg.max_image_dimension:
        raise ImageLoadError(
            f"Image is {width}x{height} pixels; the maximum dimension is "
            f"{cfg.max_image_dimension}."
        )

    return image
