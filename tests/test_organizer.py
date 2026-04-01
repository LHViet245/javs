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

    def test_move_subtitles_preserves_suffixes_for_matching_video_stem(
        self, tmp_path: Path
    ):
        """Subtitle moves should keep language/track suffixes for matching video stems."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        movie_folder = dest_dir / "ABP-420 [Test Studio] - Test Movie (2023)"
        movie_folder.mkdir()

        video_path = source_dir / "ABP-420.mp4"
        video_path.write_bytes(b"video")
        matching_srt = source_dir / "ABP-420.srt"
        matching_srt.write_text("matching", encoding="utf-8")
        matching_ja_srt = source_dir / "ABP-420.ja.srt"
        matching_ja_srt.write_text("matching-ja", encoding="utf-8")
        matching_vi_srt = source_dir / "ABP-420.vi.srt"
        matching_vi_srt.write_text("matching-vi", encoding="utf-8")
        matching_ass = source_dir / "ABP-420.eng.ass"
        matching_ass.write_text("matching-ass", encoding="utf-8")
        unrelated_srt = source_dir / "SSIS-001.srt"
        unrelated_srt.write_text("unrelated", encoding="utf-8")

        file = ScannedFile(
            path=video_path,
            filename=video_path.name,
            basename=video_path.stem,
            extension=video_path.suffix,
            directory=source_dir,
            size_bytes=video_path.stat().st_size,
            movie_id="ABP-420",
        )
        paths = self.organizer.build_sort_paths(
            file,
            MovieData(
                id="ABP-420",
                title="Test Movie",
                maker="Test Studio",
                release_date=date(2023, 6, 15),
                source="test",
            ),
            dest_dir,
        )
        paths.folder_path.mkdir(parents=True, exist_ok=True)

        self.organizer._move_subtitles(file, paths)

        assert (paths.folder_path / f"{paths.file_name}.srt").read_text(
            encoding="utf-8"
        ) == "matching"
        assert (paths.folder_path / f"{paths.file_name}.ja.srt").read_text(
            encoding="utf-8"
        ) == "matching-ja"
        assert (paths.folder_path / f"{paths.file_name}.vi.srt").read_text(
            encoding="utf-8"
        ) == "matching-vi"
        assert (paths.folder_path / f"{paths.file_name}.eng.ass").read_text(
            encoding="utf-8"
        ) == "matching-ass"
        assert not matching_srt.exists()
        assert not matching_ja_srt.exists()
        assert not matching_vi_srt.exists()
        assert not matching_ass.exists()
        assert unrelated_srt.exists()

    def test_move_subtitles_does_not_overwrite_existing_destination_subtitle(
        self, tmp_path: Path
    ):
        """Subtitle collisions should leave the source subtitle untouched."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        movie_folder = dest_dir / "ABP-420 [Test Studio] - Test Movie (2023)"
        movie_folder.mkdir()

        video_path = source_dir / "ABP-420.mp4"
        video_path.write_bytes(b"video")
        source_subtitle = source_dir / "ABP-420.ja.srt"
        source_subtitle.write_text("source", encoding="utf-8")

        file = ScannedFile(
            path=video_path,
            filename=video_path.name,
            basename=video_path.stem,
            extension=video_path.suffix,
            directory=source_dir,
            size_bytes=video_path.stat().st_size,
            movie_id="ABP-420",
        )
        paths = self.organizer.build_sort_paths(
            file,
            MovieData(
                id="ABP-420",
                title="Test Movie",
                maker="Test Studio",
                release_date=date(2023, 6, 15),
                source="test",
            ),
            dest_dir,
        )
        paths.folder_path.mkdir(parents=True, exist_ok=True)
        destination_subtitle = paths.folder_path / f"{paths.file_name}.ja.srt"
        destination_subtitle.write_text("existing", encoding="utf-8")

        self.organizer._move_subtitles(file, paths)

        assert destination_subtitle.read_text(encoding="utf-8") == "existing"
        assert not (paths.folder_path / f"{paths.file_name}.srt").exists()
        assert source_subtitle.exists()
        assert source_subtitle.read_text(encoding="utf-8") == "source"
