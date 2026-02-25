"""Image processing service: poster cropping from cover thumbnails.

Replaces Javinizer's external crop.py Python script that was called via subprocess.
"""

from __future__ import annotations

from pathlib import Path

from javs.utils.logging import get_logger

logger = get_logger(__name__)


def crop_poster(source_path: Path, dest_path: Path) -> None:
    """Crop the right portion of a cover image to create a poster.

    JAV cover images are typically wide (landscape). The poster is created
    by cropping the right half, which usually contains the main actress.

    Args:
        source_path: Path to the source cover image.
        dest_path: Path to save the cropped poster.
    """
    try:
        from PIL import Image

        with Image.open(source_path) as img:
            width, height = img.size

            # Crop the right half of the image for the poster
            left = width // 2
            box = (left, 0, width, height)
            poster = img.crop(box)

            dest_path.parent.mkdir(parents=True, exist_ok=True)
            poster.save(dest_path, "JPEG", quality=95)
            logger.debug("poster_cropped", source=str(source_path), dest=str(dest_path))
    except ImportError:
        logger.error("pillow_not_installed", msg="Install Pillow: pip install Pillow")
    except Exception as exc:
        logger.error("crop_error", source=str(source_path), error=str(exc))
