"""Tests for file organizer path generation."""

from datetime import date
from pathlib import Path

from javs.config import JavsConfig
from javs.core.organizer import FileOrganizer
from javs.models.file import ScannedFile
from javs.models.movie import MovieData


class TestFileOrganizer:
    """Test path generation and template formatting."""

    def setup_method(self):
        self.config = JavsConfig()
        self.organizer = FileOrganizer(self.config)

    def test_build_sort_paths(self):
        """sort paths should be generated correctly from templates."""
        file = ScannedFile(
            path=Path("/input/ABP-420.mp4"),
            filename="ABP-420.mp4",
            basename="ABP-420",
            extension=".mp4",
            directory=Path("/input"),
            size_bytes=1024 * 1024,
            movie_id="ABP-420",
        )
        data = MovieData(
            id="ABP-420",
            title="Test Movie",
            maker="Test Studio",
            release_date=date(2023, 6, 15),
            source="test",
        )
        dest = Path("/output")
        paths = self.organizer.build_sort_paths(file, data, dest)

        assert "ABP-420" in str(paths.folder_path)
        assert paths.file_path.suffix == ".mp4"
        assert paths.nfo_path.suffix == ".nfo"

    def test_part_number_in_filename(self):
        """Multi-part files should have part number in filename."""
        file = ScannedFile(
            path=Path("/input/ABP-420-pt2.mp4"),
            filename="ABP-420-pt2.mp4",
            basename="ABP-420-pt2",
            extension=".mp4",
            directory=Path("/input"),
            size_bytes=1024 * 1024,
            movie_id="ABP-420",
            part_number=2,
        )
        data = MovieData(id="ABP-420", title="Test", source="test")
        dest = Path("/output")
        paths = self.organizer.build_sort_paths(file, data, dest)

        assert "pt2" in paths.file_name
