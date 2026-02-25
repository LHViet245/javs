"""File scanner: discovers video files and extracts movie IDs from filenames.

Replaces Javinizer's Get-JVItem.ps1 + Convert-JVTitle.ps1.
"""

from __future__ import annotations

import re
from pathlib import Path

from javs.config.models import MatchConfig
from javs.models.file import ScannedFile
from javs.utils.logging import get_logger

logger = get_logger(__name__)

# Default regex patterns for extracting JAV IDs from filenames
DEFAULT_PATTERNS = [
    # Numeric prefix: 259LUXU-1234 (must be before standard pattern)
    r"(\d{3}[a-zA-Z]{3,5})-?(\d{3,5})",
    # Standard: ABC-123, ABC-1234, T28-123
    r"([a-zA-Z]{2,10})-(\d{3,5})",
    # Uncensored/FC2: 123456-789
    r"(\d{6,})-(\d{3,4})",
    # No dash: ABC123 or ABC1234
    r"([a-zA-Z]{2,10})(\d{3,5})",
    # T28 special: T28-123
    r"(T28)-(\d{3})",
]

# Pattern for part/disc number detection
PART_PATTERNS = [
    r"[-_. ](?:pt|part|cd|disc|disk)[-_. ]?(\d{1,2})",
    r"[-_. ](\d{1,2})of\d{1,2}",
    r"[-_. ]([a-c])$",  # a, b, c suffix
]


class FileScanner:
    """Scans directories for video files and extracts movie IDs.

    Handles:
    - File extension filtering
    - Minimum file size filtering
    - Excluded filename patterns
    - JAV ID extraction using configurable regex
    - Multi-part movie detection
    """

    def __init__(self, config: MatchConfig | None = None) -> None:
        self.config = config or MatchConfig()

    def scan(
        self,
        path: Path,
        recurse: bool = False,
        depth: int | None = None,
    ) -> list[ScannedFile]:
        """Scan a directory for matching video files.

        Args:
            path: Directory or single file path.
            recurse: Whether to scan subdirectories.
            depth: Maximum recursion depth (None = unlimited).

        Returns:
            List of ScannedFile objects with extracted movie IDs.
        """
        path = Path(path)
        if not path.exists():
            logger.error("scan_path_not_found", path=str(path))
            return []

        if path.is_file():
            result = self._process_file(path)
            return [result] if result else []

        # Collect matching files
        files = self._collect_files(path, recurse, depth)
        results: list[ScannedFile] = []

        for file_path in files:
            scanned = self._process_file(file_path)
            if scanned:
                results.append(scanned)

        logger.info("scan_complete", count=len(results), path=str(path))
        return results

    def _collect_files(
        self,
        directory: Path,
        recurse: bool,
        depth: int | None,
    ) -> list[Path]:
        """Collect all matching files from a directory."""
        extensions = set(self.config.included_extensions)
        min_size = self.config.minimum_file_size_mb * 1024 * 1024
        excluded = self.config.excluded_patterns

        # Build combined exclusion regex
        exclude_re = None
        if excluded:
            exclude_re = re.compile("|".join(excluded), re.IGNORECASE)

        files: list[Path] = []

        if recurse:
            if depth is not None:
                # Manual depth-limited recursion
                def _walk(dir_path: Path, current_depth: int) -> None:
                    if current_depth > depth:
                        return
                    try:
                        for item in sorted(dir_path.iterdir()):
                            if item.is_file():
                                files.append(item)
                            elif item.is_dir():
                                _walk(item, current_depth + 1)
                    except PermissionError:
                        pass

                _walk(directory, 0)
            else:
                files = [f for f in directory.rglob("*") if f.is_file()]
        else:
            files = [f for f in directory.iterdir() if f.is_file()]

        # Filter by extension, size, and exclusion patterns
        filtered = []
        for f in files:
            if f.suffix.lower() not in extensions:
                continue
            if f.stat().st_size < min_size:
                continue
            if exclude_re and exclude_re.search(f.name):
                continue
            filtered.append(f)

        return sorted(filtered)

    def _process_file(self, file_path: Path) -> ScannedFile | None:
        """Extract movie ID from a single file and build ScannedFile."""
        movie_id, part_number = self.extract_id(file_path.stem)
        if not movie_id:
            logger.debug("no_id_extracted", file=file_path.name)
            return None

        try:
            stat = file_path.stat()
        except OSError:
            return None

        return ScannedFile(
            path=file_path,
            filename=file_path.name,
            basename=file_path.stem,
            extension=file_path.suffix,
            directory=file_path.parent,
            size_bytes=stat.st_size,
            movie_id=movie_id,
            part_number=part_number,
        )

    def extract_id(self, filename: str) -> tuple[str | None, int | None]:
        """Extract a movie ID and optional part number from a filename.

        Args:
            filename: Base filename without extension.

        Returns:
            Tuple of (movie_id, part_number) or (None, None).
        """
        # Use custom regex if enabled
        if self.config.regex_enabled and self.config.regex:
            return self._extract_with_custom_regex(filename)

        return self._extract_with_defaults(filename)

    def _extract_with_custom_regex(self, filename: str) -> tuple[str | None, int | None]:
        """Extract using user-configured regex pattern."""
        pattern = self.config.regex.pattern
        id_group = self.config.regex.id_match_group
        pt_group = self.config.regex.part_match_group

        match = re.search(pattern, filename, re.IGNORECASE)
        if not match:
            return None, None

        movie_id = match.group(id_group) if id_group <= len(match.groups()) else None
        part = None
        if pt_group <= len(match.groups()):
            pt_str = match.group(pt_group)
            if pt_str and pt_str.isdigit():
                part = int(pt_str)

        if movie_id:
            movie_id = movie_id.upper()

        return movie_id, part

    def _extract_with_defaults(self, filename: str) -> tuple[str | None, int | None]:
        """Extract using built-in JAV ID patterns."""
        clean = filename.strip()

        # Try each pattern
        for pattern in DEFAULT_PATTERNS:
            match = re.search(pattern, clean, re.IGNORECASE)
            if match:
                prefix = match.group(1).upper()
                number = match.group(2).lstrip("0") or "0"
                number = number.zfill(3)
                movie_id = f"{prefix}-{number}"

                # Check for part number
                part = self._extract_part_number(clean)
                return movie_id, part

        return None, None

    @staticmethod
    def _extract_part_number(filename: str) -> int | None:
        """Extract part/disc number from filename."""
        for pattern in PART_PATTERNS:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                val = match.group(1)
                if val.isdigit():
                    return int(val)
                # Letter-based: a=1, b=2, c=3
                return ord(val.lower()) - ord("a") + 1
        return None
