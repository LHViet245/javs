"""Tests for data aggregator."""

from javs.config import JavsConfig
from javs.core.aggregator import DataAggregator
from javs.models.movie import MovieData


class TestDataAggregator:
    """Test priority-based data aggregation."""

    def setup_method(self):
        self.config = JavsConfig()
        self.aggregator = DataAggregator(self.config)

    def test_single_result(self):
        """Single result should pass through with post-processing."""
        data = MovieData(
            id="ABP-420",
            title="Test",
            source="r18dev",
        )
        result = self.aggregator.merge([data])
        assert result.id == "ABP-420"
        assert result.title == "Test"

    def test_priority_merge(self):
        """Higher priority source should win for each field."""
        data1 = MovieData(
            id="ABP-420",
            title="R18 Title",
            maker="R18 Studio",
            source="r18dev",
        )
        data2 = MovieData(
            id="ABP-420",
            title="Javlib Title",
            maker="Javlib Studio",
            description="Javlib description",
            source="javlibrary",
        )

        result = self.aggregator.merge([data1, data2])
        # r18dev has higher priority for title
        assert result.title == "R18 Title"

    def test_fallback_to_any_source(self):
        """If field not in priority list, use any source that has it."""
        data = MovieData(
            id="ABP-420",
            title="Title",
            series="Test Series",
            source="r18dev",
        )
        result = self.aggregator.merge([data])
        assert result.series == "Test Series"

    def test_empty_results(self):
        """Empty input should return empty MovieData."""
        result = self.aggregator.merge([])
        assert result.id == ""

    def test_display_name_generation(self):
        """Display name should be generated from template."""
        data = MovieData(
            id="ABP-420",
            title="Test Movie",
            source="test",
        )
        result = self.aggregator.merge([data])
        assert "ABP-420" in result.display_name
        assert "Test Movie" in result.display_name

    def test_genre_filtering(self):
        """Ignored genre patterns should be filtered out."""
        data = MovieData(
            id="ABP-420",
            genres=["Drama", "Featured Actress", "Hi-Def Streaming"],
            source="test",
        )
        result = self.aggregator.merge([data])
        assert "Drama" in result.genres
        assert "Featured Actress" not in result.genres

    def test_merge_prefers_non_empty(self):
        """Merge should skip empty values and pick first non-empty."""
        data1 = MovieData(
            id="ABP-420",
            title="",
            source="r18dev",
        )
        data2 = MovieData(
            id="ABP-420",
            title="Actual Title",
            source="javlibrary",
        )
        result = self.aggregator.merge([data1, data2])
        assert result.title == "Actual Title"
