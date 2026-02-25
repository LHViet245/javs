"""Tests for file scanner and ID extraction."""

import pytest

from javs.config.models import MatchConfig
from javs.core.scanner import FileScanner


class TestFileScanner:
    """Test FileScanner functionality."""

    def setup_method(self):
        self.scanner = FileScanner()

    # ─── ID Extraction Tests ─────────────────────────────

    @pytest.mark.parametrize(
        "filename, expected_id",
        [
            ("ABP-420", "ABP-420"),
            ("abp-420", "ABP-420"),
            ("ABP420", "ABP-420"),
            ("abc-123.mp4", "ABC-123"),
            ("SSIS-001", "SSIS-001"),
            ("SSIS-1234", "SSIS-1234"),
            ("T28-123", "T28-123"),
            ("259LUXU-1234", "259LUXU-1234"),
            ("MIDV-0103", "MIDV-103"),
            ("[Thz.la]ABP-420", "ABP-420"),
            ("Some.Random.Text.ABP-420.1080p", "ABP-420"),
        ],
    )
    def test_extract_id(self, filename, expected_id):
        """ID extraction should handle various filename formats."""
        movie_id, _ = self.scanner.extract_id(filename)
        assert movie_id == expected_id

    @pytest.mark.parametrize(
        "filename, expected_part",
        [
            ("ABP-420-pt1", 1),
            ("ABP-420-pt2", 2),
            ("ABP-420 cd1", 1),
            ("ABP-420 cd2", 2),
            ("ABP-420", None),
        ],
    )
    def test_extract_part_number(self, filename, expected_part):
        """Part number detection should work."""
        _, part = self.scanner.extract_id(filename)
        assert part == expected_part

    def test_scan_directory(self, tmp_path):
        """Scanner should find matching video files."""
        # Create test files
        (tmp_path / "ABP-420.mp4").write_bytes(b"fake video")
        (tmp_path / "SSIS-001.mkv").write_bytes(b"fake video")
        (tmp_path / "readme.txt").write_text("not a video")
        (tmp_path / "photo.jpg").write_bytes(b"not a video")

        config = MatchConfig(minimum_file_size_mb=0)
        scanner = FileScanner(config)
        results = scanner.scan(tmp_path)

        assert len(results) == 2
        ids = {r.movie_id for r in results}
        assert "ABP-420" in ids
        assert "SSIS-001" in ids

    def test_scan_recursive(self, tmp_path):
        """Scanner with recurse should scan subdirectories."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "ABP-420.mp4").write_bytes(b"fake")
        (tmp_path / "SSIS-001.mp4").write_bytes(b"fake")

        config = MatchConfig(minimum_file_size_mb=0)
        scanner = FileScanner(config)

        # Without recurse
        results_flat = scanner.scan(tmp_path, recurse=False)
        assert len(results_flat) == 1

        # With recurse
        results_deep = scanner.scan(tmp_path, recurse=True)
        assert len(results_deep) == 2

    def test_scan_respects_excluded_patterns(self, tmp_path):
        """Excluded patterns should filter out files."""
        (tmp_path / "ABP-420.mp4").write_bytes(b"fake")
        (tmp_path / "ABP-420-trailer.mp4").write_bytes(b"fake")

        config = MatchConfig(
            minimum_file_size_mb=0,
            excluded_patterns=[r".*trailer.*"],
        )
        scanner = FileScanner(config)
        results = scanner.scan(tmp_path)

        assert len(results) == 1
        assert results[0].movie_id == "ABP-420"
