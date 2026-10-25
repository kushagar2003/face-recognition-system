"""
Quick check for the image loader. Run from the project root.

    python -m scripts.check_image_loader
        Checks the error path only (a file that does not exist).

    python -m scripts.check_image_loader data\\sample_images\\photo.jpg
        Loads one image and reports its size.

Prints only pass or fail and the file name. It never prints image contents.
"""

import sys
from pathlib import Path

from ai_pipeline.image_loader import ImageLoadError, load_image


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        path = Path(argv[1])
        try:
            image = load_image(path)
        except ImageLoadError as exc:
            print(f"FAILED: {path.name}: {exc}")
            return 1
        height, width = image.shape[:2]
        print(f"SUCCESS: loaded {path.name} ({width}x{height} pixels, 3 colour channels).")
        return 0

    try:
        load_image(Path("data/sample_images/does_not_exist.jpg"))
    except ImageLoadError as exc:
        print(f"SUCCESS: missing file was rejected as expected. Message: {exc}")
        return 0
    print("FAILED: a missing file was not rejected.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
