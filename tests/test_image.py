"""Tests for poster image cropping."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from javs.services.image import crop_poster


class TestCropPoster:
    """Verify poster crop output and error tolerance."""

    def test_crop_poster_saves_right_half_of_cover(self, tmp_path: Path) -> None:
        source = tmp_path / "cover.jpg"
        dest = tmp_path / "nested" / "poster.jpg"

        with Image.new("RGB", (100, 40), color="red") as img:
            for x in range(50, 100):
                for y in range(40):
                    img.putpixel((x, y), (0, 0, 255))
            img.save(source, "JPEG")

        crop_poster(source, dest)

        assert dest.exists()
        with Image.open(dest) as poster:
            assert poster.size == (50, 40)
            blue, red = poster.getpixel((10, 10))[2], poster.getpixel((10, 10))[0]
            assert blue > red

    def test_crop_poster_handles_missing_source_without_raising(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing.jpg"
        dest = tmp_path / "poster.jpg"

        crop_poster(missing, dest)

        assert not dest.exists()
