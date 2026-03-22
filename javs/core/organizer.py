"""File organizer: moves, renames, and downloads assets for sorted movies.

Replaces Javinizer's Set-JVMovie.ps1 (536 lines).
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from javs.config.models import JavsConfig
from javs.core.nfo import NfoGenerator
from javs.models.file import ScannedFile, SortPaths
from javs.models.movie import MovieData
from javs.services.http import HttpClient
from javs.utils.logging import get_logger
from javs.utils.string import format_template, sanitize_filename

logger = get_logger(__name__)


class FileOrganizer:
    """Organize video files: generate paths, create NFO, download media, move files.

    Handles the full sorting pipeline:
    1. Generate destination paths from format templates
    2. Create destination directory
    3. Generate and write NFO file
    4. Download cover/poster/screenshot/trailer
    5. Move/rename the video file
    6. Move associated subtitle files
    """

    def __init__(self, config: JavsConfig, http: HttpClient | None = None) -> None:
        self.config = config
        self.http = http or HttpClient()
        self.nfo_gen = NfoGenerator(config.sort.metadata.nfo)

    def build_sort_paths(
        self,
        file: ScannedFile,
        data: MovieData,
        dest_root: Path,
    ) -> SortPaths:
        """Calculate all destination paths for a sorted movie.

        Args:
            file: The scanned source file.
            data: Aggregated movie metadata.
            dest_root: Root destination directory.

        Returns:
            SortPaths with all computed paths.
        """
        fmt = self.config.sort.format
        template_data = self._build_template_data(data)

        # Folder name
        folder_name = sanitize_filename(
            format_template(
                fmt.folder,
                template_data,
                fmt.delimiter,
                fmt.max_title_length,
            )
        )

        # File name (without extension)
        file_name = sanitize_filename(
            format_template(fmt.file, template_data, fmt.delimiter, fmt.max_title_length)
        )

        # Handle part numbers
        if file.part_number and file.part_number > 0:
            file_name = f"{file_name}-pt{file.part_number}"

        folder_path = dest_root / folder_name

        # NFO name
        nfo_name = sanitize_filename(
            format_template(fmt.nfo, template_data, fmt.delimiter, fmt.max_title_length)
        )

        # Thumb/poster names
        thumb_name = sanitize_filename(
            format_template(fmt.thumb_img, template_data, fmt.delimiter, fmt.max_title_length)
        )

        # Poster paths
        poster_paths = []
        for poster_fmt in fmt.poster_img:
            poster_name = sanitize_filename(
                format_template(poster_fmt, template_data, fmt.delimiter, fmt.max_title_length)
            )
            poster_paths.append(folder_path / f"{poster_name}.jpg")

        return SortPaths(
            folder_path=folder_path,
            folder_name=folder_name,
            file_path=folder_path / f"{file_name}{file.extension}",
            file_name=file_name,
            nfo_path=folder_path / f"{nfo_name}.nfo",
            thumb_path=folder_path / f"{thumb_name}.jpg",
            poster_paths=poster_paths,
            trailer_path=(
                folder_path
                / f"{sanitize_filename(format_template(fmt.trailer_vid, template_data))}.mp4"
                if self.config.sort.download.trailer_vid
                else None
            ),
            screenshot_folder_path=folder_path / fmt.screenshot_folder,
            screenshot_img_name=fmt.screenshot_img,
            actor_folder_path=folder_path / fmt.actress_img_folder,
            parent_path=file.directory,
            part_number=file.part_number or 0,
        )

    def build_update_paths(
        self,
        file: ScannedFile,
        data: MovieData,
    ) -> SortPaths:
        """Calculate sidecar paths for an already-sorted movie in its current folder."""
        fmt = self.config.sort.format
        template_data = self._build_template_data(data)
        folder_path = file.directory
        thumb_name = sanitize_filename(
            format_template(fmt.thumb_img, template_data, fmt.delimiter, fmt.max_title_length)
        )
        poster_paths = []
        for poster_fmt in fmt.poster_img:
            poster_name = sanitize_filename(
                format_template(poster_fmt, template_data, fmt.delimiter, fmt.max_title_length)
            )
            poster_paths.append(folder_path / f"{poster_name}.jpg")

        return SortPaths(
            folder_path=folder_path,
            folder_name=folder_path.name,
            file_path=file.path,
            file_name=file.basename,
            nfo_path=self._resolve_update_nfo_path(file, data),
            thumb_path=folder_path / f"{thumb_name}.jpg",
            poster_paths=poster_paths,
            trailer_path=(
                folder_path
                / f"{sanitize_filename(format_template(fmt.trailer_vid, template_data))}.mp4"
                if self.config.sort.download.trailer_vid
                else None
            ),
            screenshot_folder_path=folder_path / fmt.screenshot_folder,
            screenshot_img_name=fmt.screenshot_img,
            actor_folder_path=folder_path / fmt.actress_img_folder,
            parent_path=file.directory,
            part_number=file.part_number or 0,
        )

    async def sort_movie(
        self,
        file: ScannedFile,
        data: MovieData,
        dest_root: Path,
        force: bool = False,
        preview: bool = False,
    ) -> SortPaths:
        """Execute the full sort pipeline for a single movie.

        Args:
            file: Source video file.
            data: Aggregated movie metadata.
            dest_root: Root destination directory.
            force: Overwrite existing files.
            preview: Dry run — compute paths but don't move anything.

        Returns:
            Computed SortPaths.
        """
        sort_paths = self.build_sort_paths(file, data, dest_root)

        if preview:
            logger.info(
                "preview_sort",
                id=data.id,
                source=str(file.path),
                dest=str(sort_paths.file_path),
            )
            return sort_paths

        # 1. Create destination directory
        sort_paths.folder_path.mkdir(parents=True, exist_ok=True)
        logger.debug("directory_created", path=str(sort_paths.folder_path))

        # 2. Generate and write NFO
        if self.config.sort.metadata.nfo.create:
            await self._write_nfo(data, sort_paths, file, force)

        # 3. Download cover/thumbnail
        if self.config.sort.download.thumb_img and data.cover_url:
            await self._download_thumb(data, sort_paths, force)

        # 4. Download and crop poster
        if self.config.sort.download.poster_img and data.cover_url:
            await self._create_posters(sort_paths, force)

        # 5. Download actress images
        if self.config.sort.download.actress_img and data.actresses:
            await self._download_actress_images(data, sort_paths, force)

        # 6. Download screenshots
        if self.config.sort.download.screenshot_img and data.screenshot_urls:
            await self._download_screenshots(data, sort_paths, force)

        # 7. Download trailer
        if self.config.sort.download.trailer_vid and data.trailer_url and sort_paths.trailer_path:
            await self._download_trailer(data, sort_paths, force)

        # 8. Move subtitles
        if self.config.sort.move_subtitles:
            self._move_subtitles(file, sort_paths)

        # 9. Move/rename the video file
        if self.config.sort.rename_file or self.config.sort.move_to_folder:
            self._move_video(file, sort_paths, force)

        logger.info(
            "sort_complete",
            id=data.id,
            source=str(file.path),
            dest=str(sort_paths.file_path),
        )
        return sort_paths

    async def update_movie(
        self,
        file: ScannedFile,
        data: MovieData,
        force: bool = False,
        preview: bool = False,
        refresh_images: bool = False,
        refresh_trailer: bool = False,
    ) -> SortPaths:
        """Refresh sidecars for an already-sorted movie without moving media files."""
        update_paths = self.build_update_paths(file, data)

        if preview:
            logger.info(
                "preview_update",
                id=data.id,
                source=str(file.path),
                folder=str(update_paths.folder_path),
                nfo=str(update_paths.nfo_path),
            )
            return update_paths

        image_force = force or refresh_images
        trailer_force = force or refresh_trailer

        update_paths.folder_path.mkdir(parents=True, exist_ok=True)

        if self.config.sort.metadata.nfo.create:
            await self._write_nfo(data, update_paths, file, force=True)

        if self.config.sort.download.thumb_img and data.cover_url:
            await self._download_thumb(data, update_paths, image_force)

        if self.config.sort.download.poster_img and data.cover_url:
            await self._create_posters(update_paths, image_force)

        if self.config.sort.download.actress_img and data.actresses:
            await self._download_actress_images(data, update_paths, image_force)

        if self.config.sort.download.screenshot_img and data.screenshot_urls:
            await self._download_screenshots(data, update_paths, image_force)

        if (
            self.config.sort.download.trailer_vid
            and data.trailer_url
            and update_paths.trailer_path
        ):
            await self._download_trailer(data, update_paths, trailer_force)

        logger.info(
            "update_complete",
            id=data.id,
            source=str(file.path),
            folder=str(update_paths.folder_path),
        )
        return update_paths

    # ─── Private helpers ─────────────────────────────────────────

    def _build_template_data(self, data: MovieData) -> dict:
        """Build template substitution dict from MovieData."""
        actress_names = []
        for a in data.actresses:
            actress_names.append(a.full_name)

        return {
            "id": data.id,
            "title": data.title or "",
            "maker": data.maker or "",
            "studio": data.maker or "",
            "label": data.label or "",
            "series": data.series or "",
            "year": str(data.release_year) if data.release_year else "",
            "director": data.director or "",
            "actresses": actress_names,
        }

    def _resolve_update_nfo_path(self, file: ScannedFile, data: MovieData) -> Path:
        """Pick the existing NFO path when possible, otherwise create one in the current folder."""
        folder_path = file.directory
        per_file_candidate = folder_path / f"{file.basename}.nfo"
        if per_file_candidate.exists():
            return per_file_candidate

        existing_nfos = sorted(folder_path.glob("*.nfo"))
        if len(existing_nfos) == 1:
            return existing_nfos[0]

        fmt = self.config.sort.format
        template_data = self._build_template_data(data)
        nfo_name = sanitize_filename(
            format_template(fmt.nfo, template_data, fmt.delimiter, fmt.max_title_length)
        )
        return folder_path / f"{nfo_name}.nfo"

    async def _write_nfo(
        self,
        data: MovieData,
        paths: SortPaths,
        file: ScannedFile,
        force: bool,
    ) -> None:
        """Generate and write NFO file."""
        if paths.nfo_path.exists() and not force:
            return
        try:
            original_path = str(file.path) if self.config.sort.metadata.nfo.original_path else None
            nfo_content = self.nfo_gen.generate(data, original_path)
            await asyncio.to_thread(paths.nfo_path.write_text, nfo_content, encoding="utf-8")
            logger.debug("nfo_created", path=str(paths.nfo_path))
        except Exception as exc:
            logger.error("nfo_error", id=data.id, error=str(exc))

    async def _download_thumb(self, data: MovieData, paths: SortPaths, force: bool) -> None:
        """Download cover thumbnail."""
        if paths.thumb_path.exists() and not force:
            return
        if paths.part_number > 1:
            return  # Only first part downloads the thumb

        await self.http.download(
            data.cover_url,  # type: ignore
            paths.thumb_path,
            timeout=self.config.sort.download.timeout_seconds,
        )

    async def _create_posters(self, paths: SortPaths, force: bool) -> None:
        """Crop poster image from thumbnail."""
        for poster_path in paths.poster_paths:
            if poster_path.exists() and not force:
                continue
            if paths.part_number > 1:
                continue
            if not paths.thumb_path.exists():
                continue

            try:
                from javs.services.image import crop_poster

                crop_poster(paths.thumb_path, poster_path)
                logger.debug("poster_created", path=str(poster_path))
            except Exception as exc:
                logger.error("poster_error", error=str(exc))

    async def _download_actress_images(
        self, data: MovieData, paths: SortPaths, force: bool
    ) -> None:
        """Download actress thumbnail images."""
        if not paths.actor_folder_path:
            return
        paths.actor_folder_path.mkdir(parents=True, exist_ok=True)

        for actress in data.actresses:
            if not actress.thumb_url:
                continue
            name = actress.full_name.replace(" ", "_")
            dest = paths.actor_folder_path / f"{name}.jpg"
            if dest.exists() and not force:
                continue
            await self.http.download(actress.thumb_url, dest)

    async def _download_screenshots(self, data: MovieData, paths: SortPaths, force: bool) -> None:
        """Download screenshot images."""
        if not paths.screenshot_folder_path:
            return
        paths.screenshot_folder_path.mkdir(parents=True, exist_ok=True)

        padding = self.config.sort.format.screenshot_padding
        for idx, url in enumerate(data.screenshot_urls, start=1):
            padded = str(idx).zfill(padding)
            dest = paths.screenshot_folder_path / f"{paths.screenshot_img_name}{padded}.jpg"
            if dest.exists() and not force:
                continue
            await self.http.download(url, dest)

    async def _download_trailer(self, data: MovieData, paths: SortPaths, force: bool) -> None:
        """Download trailer video."""
        if not paths.trailer_path or (paths.trailer_path.exists() and not force):
            return
        if paths.part_number > 1:
            return
        if data.trailer_url:
            await self.http.download(
                data.trailer_url,
                paths.trailer_path,
                timeout=self.config.sort.download.timeout_seconds,
            )

    def _move_subtitles(self, file: ScannedFile, paths: SortPaths) -> None:
        """Find and move subtitle files matching the video to the destination folder.

        Only moves subtitles whose stem starts with the video file's stem,
        supporting patterns like: ABC-123.srt, ABC-123.chi.srt, ABC-123.eng.ass
        """
        subtitle_exts = {".ass", ".ssa", ".srt", ".smi", ".vtt"}
        video_stem = file.path.stem.lower()

        try:
            for sub_file in file.directory.iterdir():
                if sub_file.suffix.lower() not in subtitle_exts:
                    continue
                sub_stem = sub_file.stem.lower()
                # Match: sub stem starts with video stem
                # Handles: ABC-123.srt, ABC-123.chi.srt, ABC-123.eng.ass
                if not sub_stem.startswith(video_stem):
                    continue
                dest = paths.folder_path / f"{paths.file_name}{sub_file.suffix}"
                if not dest.exists():
                    shutil.move(str(sub_file), str(dest))
                    logger.debug("subtitle_moved", src=str(sub_file), dest=str(dest))
        except Exception as exc:
            logger.error("subtitle_move_error", error=str(exc))

    def _move_video(self, file: ScannedFile, paths: SortPaths, force: bool) -> None:
        """Move/rename the video file."""
        if paths.file_path.exists() and not force:
            logger.warning("dest_exists", dest=str(paths.file_path))
            return
        try:
            shutil.move(str(file.path), str(paths.file_path))
            logger.info("file_moved", src=str(file.path), dest=str(paths.file_path))
        except Exception as exc:
            logger.error("file_move_error", src=str(file.path), error=str(exc))
