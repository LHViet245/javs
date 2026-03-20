"""Tests for file organizer path generation."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from javs.config import JavsConfig
from javs.core.organizer import FileOrganizer
from javs.models.file import ScannedFile
from javs.models.movie import Actress, MovieData


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

    def test_move_subtitles_only_moves_matching_video_stem(self, tmp_path: Path):
        """Subtitle moves should be limited to files matching the video stem."""
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

        assert (paths.folder_path / f"{paths.file_name}.srt").exists()
        assert (paths.folder_path / f"{paths.file_name}.ass").exists()
        assert unrelated_srt.exists()

    @pytest.mark.asyncio
    async def test_sort_movie_preview_skips_side_effects(self, monkeypatch, tmp_path: Path):
        """Preview mode should only compute paths without touching the filesystem."""
        file = ScannedFile(
            path=tmp_path / "ABP-420.mp4",
            filename="ABP-420.mp4",
            basename="ABP-420",
            extension=".mp4",
            directory=tmp_path,
            size_bytes=1024,
            movie_id="ABP-420",
        )
        data = MovieData(id="ABP-420", title="Preview Movie", source="test")
        file.path.write_bytes(b"video")
        dest = tmp_path / "dest"

        monkeypatch.setattr(
            self.organizer, "_write_nfo", AsyncMock(side_effect=AssertionError)
        )
        monkeypatch.setattr(
            self.organizer, "_download_thumb", AsyncMock(side_effect=AssertionError)
        )
        monkeypatch.setattr(
            self.organizer, "_create_posters", AsyncMock(side_effect=AssertionError)
        )
        monkeypatch.setattr(
            self.organizer,
            "_download_actress_images",
            AsyncMock(side_effect=AssertionError),
        )
        monkeypatch.setattr(
            self.organizer,
            "_download_screenshots",
            AsyncMock(side_effect=AssertionError),
        )
        monkeypatch.setattr(
            self.organizer, "_download_trailer", AsyncMock(side_effect=AssertionError)
        )
        monkeypatch.setattr(
            self.organizer,
            "_move_subtitles",
            lambda *_args: (_ for _ in ()).throw(AssertionError),
        )
        monkeypatch.setattr(
            self.organizer,
            "_move_video",
            lambda *_args: (_ for _ in ()).throw(AssertionError),
        )

        paths = await self.organizer.sort_movie(file, data, dest, preview=True)

        assert paths.file_path == paths.folder_path / "ABP-420.mp4"
        assert not paths.folder_path.exists()
        assert file.path.exists()

    @pytest.mark.asyncio
    async def test_write_nfo_includes_original_path_when_enabled(
        self, monkeypatch, tmp_path: Path
    ):
        self.config.sort.metadata.nfo.original_path = True
        organizer = FileOrganizer(self.config)
        source = tmp_path / "ABP-420.mp4"
        source.write_bytes(b"video")

        async def fake_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        from javs.core import organizer as organizer_module

        monkeypatch.setattr(organizer_module.asyncio, "to_thread", fake_to_thread)
        paths = organizer.build_sort_paths(
            ScannedFile(
                path=source,
                filename=source.name,
                basename=source.stem,
                extension=source.suffix,
                directory=tmp_path,
                size_bytes=source.stat().st_size,
                movie_id="ABP-420",
            ),
            MovieData(id="ABP-420", title="Movie", source="test"),
            tmp_path / "dest",
        )
        paths.folder_path.mkdir(parents=True, exist_ok=True)

        await organizer._write_nfo(
            MovieData(id="ABP-420", title="Movie", source="test"),
            paths,
            ScannedFile(
                path=source,
                filename=source.name,
                basename=source.stem,
                extension=source.suffix,
                directory=tmp_path,
                size_bytes=source.stat().st_size,
                movie_id="ABP-420",
            ),
            force=False,
        )

        assert paths.nfo_path.exists()
        assert str(source) in paths.nfo_path.read_text(encoding="utf-8")

    @pytest.mark.asyncio
    async def test_download_thumb_skips_existing_file_without_force(self, tmp_path: Path):
        http = AsyncMock()
        organizer = FileOrganizer(self.config, http=http)
        paths = organizer.build_sort_paths(
            ScannedFile(
                path=tmp_path / "ABP-420.mp4",
                filename="ABP-420.mp4",
                basename="ABP-420",
                extension=".mp4",
                directory=tmp_path,
                size_bytes=1024,
                movie_id="ABP-420",
            ),
            MovieData(id="ABP-420", title="Movie", source="test", cover_url="https://example.com/cover.jpg"),
            tmp_path / "dest",
        )
        paths.folder_path.mkdir(parents=True, exist_ok=True)
        paths.thumb_path.write_bytes(b"existing")

        await organizer._download_thumb(
            MovieData(id="ABP-420", title="Movie", source="test", cover_url="https://example.com/cover.jpg"),
            paths,
            force=False,
        )

        http.download.assert_not_called()

    @pytest.mark.asyncio
    async def test_download_thumb_uses_timeout_for_first_part(self, tmp_path: Path):
        http = AsyncMock()
        organizer = FileOrganizer(self.config, http=http)
        file = ScannedFile(
            path=tmp_path / "ABP-420.mp4",
            filename="ABP-420.mp4",
            basename="ABP-420",
            extension=".mp4",
            directory=tmp_path,
            size_bytes=1024,
            movie_id="ABP-420",
        )
        data = MovieData(
            id="ABP-420",
            title="Movie",
            source="test",
            cover_url="https://example.com/cover.jpg",
        )
        paths = organizer.build_sort_paths(file, data, tmp_path / "dest")

        await organizer._download_thumb(data, paths, force=False)

        http.download.assert_awaited_once_with(
            "https://example.com/cover.jpg",
            paths.thumb_path,
            timeout=self.config.sort.download.timeout_seconds,
        )

    @pytest.mark.asyncio
    async def test_create_posters_uses_crop_service_when_thumb_exists(
        self, monkeypatch, tmp_path: Path
    ):
        organizer = FileOrganizer(self.config)
        file = ScannedFile(
            path=tmp_path / "ABP-420.mp4",
            filename="ABP-420.mp4",
            basename="ABP-420",
            extension=".mp4",
            directory=tmp_path,
            size_bytes=1024,
            movie_id="ABP-420",
        )
        data = MovieData(id="ABP-420", title="Movie", source="test")
        paths = organizer.build_sort_paths(file, data, tmp_path / "dest")
        paths.folder_path.mkdir(parents=True, exist_ok=True)
        paths.thumb_path.write_bytes(b"thumb")
        cropped: list[tuple[Path, Path]] = []

        monkeypatch.setattr(
            "javs.services.image.crop_poster",
            lambda source, dest: cropped.append((source, dest)),
        )

        await organizer._create_posters(paths, force=False)

        assert cropped == [(paths.thumb_path, paths.poster_paths[0])]

    @pytest.mark.asyncio
    async def test_download_actress_images_only_downloads_available_thumbs(self, tmp_path: Path):
        http = AsyncMock()
        organizer = FileOrganizer(self.config, http=http)
        file = ScannedFile(
            path=tmp_path / "ABP-420.mp4",
            filename="ABP-420.mp4",
            basename="ABP-420",
            extension=".mp4",
            directory=tmp_path,
            size_bytes=1024,
            movie_id="ABP-420",
        )
        data = MovieData(
            id="ABP-420",
            title="Movie",
            source="test",
            actresses=[
                Actress(first_name="Rei", last_name="Kamiki", thumb_url="https://example.com/rei.jpg"),
                Actress(japanese_name="No Thumb"),
            ],
        )
        paths = organizer.build_sort_paths(file, data, tmp_path / "dest")

        await organizer._download_actress_images(data, paths, force=False)

        http.download.assert_awaited_once_with(
            "https://example.com/rei.jpg",
            paths.actor_folder_path / "Kamiki_Rei.jpg",
        )

    @pytest.mark.asyncio
    async def test_download_screenshots_uses_padding_in_output_names(self, tmp_path: Path):
        http = AsyncMock()
        self.config.sort.format.screenshot_padding = 2
        organizer = FileOrganizer(self.config, http=http)
        file = ScannedFile(
            path=tmp_path / "ABP-420.mp4",
            filename="ABP-420.mp4",
            basename="ABP-420",
            extension=".mp4",
            directory=tmp_path,
            size_bytes=1024,
            movie_id="ABP-420",
        )
        data = MovieData(
            id="ABP-420",
            title="Movie",
            source="test",
            screenshot_urls=["https://example.com/1.jpg", "https://example.com/2.jpg"],
        )
        paths = organizer.build_sort_paths(file, data, tmp_path / "dest")

        await organizer._download_screenshots(data, paths, force=False)

        assert http.download.await_args_list[0].args == (
            "https://example.com/1.jpg",
            paths.screenshot_folder_path / "fanart01.jpg",
        )
        assert http.download.await_args_list[1].args == (
            "https://example.com/2.jpg",
            paths.screenshot_folder_path / "fanart02.jpg",
        )

    @pytest.mark.asyncio
    async def test_download_trailer_skips_later_parts(self, tmp_path: Path):
        http = AsyncMock()
        self.config.sort.download.trailer_vid = True
        organizer = FileOrganizer(self.config, http=http)
        file = ScannedFile(
            path=tmp_path / "ABP-420-pt2.mp4",
            filename="ABP-420-pt2.mp4",
            basename="ABP-420-pt2",
            extension=".mp4",
            directory=tmp_path,
            size_bytes=1024,
            movie_id="ABP-420",
            part_number=2,
        )
        data = MovieData(
            id="ABP-420",
            title="Movie",
            source="test",
            trailer_url="https://example.com/trailer.mp4",
        )
        paths = organizer.build_sort_paths(file, data, tmp_path / "dest")

        await organizer._download_trailer(data, paths, force=False)

        http.download.assert_not_called()

    def test_move_video_keeps_source_when_destination_exists_without_force(self, tmp_path: Path):
        source = tmp_path / "ABP-420.mp4"
        source.write_bytes(b"video")
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        dest_file = dest_dir / "ABP-420.mp4"
        dest_file.write_bytes(b"existing")
        paths = self.organizer.build_sort_paths(
            ScannedFile(
                path=source,
                filename=source.name,
                basename=source.stem,
                extension=source.suffix,
                directory=tmp_path,
                size_bytes=source.stat().st_size,
                movie_id="ABP-420",
            ),
            MovieData(id="ABP-420", title="Movie", source="test"),
            tmp_path,
        )
        paths.file_path.parent.mkdir(parents=True, exist_ok=True)
        paths.file_path.write_bytes(b"existing")

        self.organizer._move_video(
            ScannedFile(
                path=source,
                filename=source.name,
                basename=source.stem,
                extension=source.suffix,
                directory=tmp_path,
                size_bytes=source.stat().st_size,
                movie_id="ABP-420",
            ),
            paths,
            force=False,
        )

        assert source.exists()
        assert paths.file_path.read_bytes() == b"existing"
