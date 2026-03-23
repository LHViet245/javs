"""Tests for data aggregator."""

import csv

from javs.config import JavsConfig
from javs.core.aggregator import DataAggregator
from javs.models.movie import Actress, ActressAlias, JapaneseAlias, MovieData


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

    def test_genre_csv_replaces_and_removes_entries(self, tmp_path):
        path = tmp_path / "genres.csv"
        path.write_text(
            "Original,Replacement\nDrama,Story\nHi-Def,\n",
            encoding="utf-8",
        )
        self.config.sort.metadata.genre_csv.enabled = True
        self.config.locations.genre_csv = str(path)
        aggregator = DataAggregator(self.config)

        result = aggregator.merge(
            [
                MovieData(
                    id="ABP-420",
                    genres=["Drama", "Hi-Def"],
                    source="test",
                )
            ]
        )

        assert result.genres == ["Story"]

    def test_genre_csv_auto_add_appends_identity_rows(self, tmp_path):
        path = tmp_path / "genres.csv"
        self.config.sort.metadata.genre_csv.enabled = True
        self.config.sort.metadata.genre_csv.auto_add = True
        self.config.locations.genre_csv = str(path)
        aggregator = DataAggregator(self.config)

        aggregator.merge([MovieData(id="ABP-420", genres=["Drama", "Rare"], source="test")])

        rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
        assert rows == [
            {"Original": "Drama", "Replacement": "Drama"},
            {"Original": "Rare", "Replacement": "Rare"},
        ]

    def test_thumb_csv_resolves_by_japanese_name(self, tmp_path):
        path = tmp_path / "thumbs.csv"
        path.write_text(
            "FullName,JapaneseName,ThumbUrl\n,神木麗,https://example.com/rei.jpg\n",
            encoding="utf-8",
        )
        self.config.sort.metadata.thumb_csv.enabled = True
        self.config.locations.thumb_csv = str(path)
        aggregator = DataAggregator(self.config)

        result = aggregator.merge(
            [
                MovieData(
                    id="ABP-420",
                    actresses=[Actress(japanese_name="神木麗")],
                    source="test",
                )
            ]
        )

        assert result.actresses[0].thumb_url == "https://example.com/rei.jpg"

    def test_thumb_csv_does_not_override_existing_scraper_thumb(self, tmp_path):
        path = tmp_path / "thumbs.csv"
        path.write_text(
            "FullName,JapaneseName,ThumbUrl\nKamiki Rei,神木麗,https://example.com/cached.jpg\n",
            encoding="utf-8",
        )
        self.config.sort.metadata.thumb_csv.enabled = True
        self.config.locations.thumb_csv = str(path)
        aggregator = DataAggregator(self.config)

        result = aggregator.merge(
            [
                MovieData(
                    id="ABP-420",
                    actresses=[
                        Actress(
                            last_name="Kamiki",
                            first_name="Rei",
                            thumb_url="https://example.com/scraper.jpg",
                        )
                    ],
                    source="test",
                )
            ]
        )

        assert result.actresses[0].thumb_url == "https://example.com/scraper.jpg"

    def test_thumb_csv_convert_alias_matches_english_alias(self, tmp_path):
        path = tmp_path / "thumbs.csv"
        path.write_text(
            "FullName,JapaneseName,ThumbUrl\nAlias Performer,,https://example.com/alias.jpg\n",
            encoding="utf-8",
        )
        self.config.sort.metadata.thumb_csv.enabled = True
        self.config.sort.metadata.thumb_csv.convert_alias = True
        self.config.locations.thumb_csv = str(path)
        aggregator = DataAggregator(self.config)

        result = aggregator.merge(
            [
                MovieData(
                    id="ABP-420",
                    actresses=[
                        Actress(
                            japanese_name="演員A",
                            english_aliases=[
                                ActressAlias(last_name="Alias", first_name="Performer")
                            ],
                        )
                    ],
                    source="test",
                )
            ]
        )

        assert result.actresses[0].thumb_url == "https://example.com/alias.jpg"

    def test_thumb_csv_convert_alias_matches_japanese_alias(self, tmp_path):
        path = tmp_path / "thumbs.csv"
        path.write_text(
            "FullName,JapaneseName,ThumbUrl\n,別名,https://example.com/alt.jpg\n",
            encoding="utf-8",
        )
        self.config.sort.metadata.thumb_csv.enabled = True
        self.config.sort.metadata.thumb_csv.convert_alias = True
        self.config.locations.thumb_csv = str(path)
        aggregator = DataAggregator(self.config)

        result = aggregator.merge(
            [
                MovieData(
                    id="ABP-420",
                    actresses=[
                        Actress(
                            japanese_name="演員A",
                            japanese_aliases=[JapaneseAlias(japanese_name="別名")],
                        )
                    ],
                    source="test",
                )
            ]
        )

        assert result.actresses[0].thumb_url == "https://example.com/alt.jpg"

    def test_thumb_csv_auto_add_appends_new_actress_rows(self, tmp_path):
        path = tmp_path / "thumbs.csv"
        self.config.sort.metadata.thumb_csv.enabled = True
        self.config.sort.metadata.thumb_csv.auto_add = True
        self.config.locations.thumb_csv = str(path)
        aggregator = DataAggregator(self.config)

        aggregator.merge(
            [
                MovieData(
                    id="ABP-420",
                    actresses=[
                        Actress(
                            last_name="Kamiki",
                            first_name="Rei",
                            japanese_name="神木麗",
                            thumb_url="https://example.com/rei.jpg",
                        )
                    ],
                    source="test",
                )
            ]
        )

        rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
        assert rows == [
            {
                "FullName": "Kamiki Rei",
                "JapaneseName": "神木麗",
                "ThumbUrl": "https://example.com/rei.jpg",
            }
        ]

    def test_thumb_csv_auto_add_avoids_duplicate_rows_in_same_run(self, tmp_path):
        path = tmp_path / "thumbs.csv"
        self.config.sort.metadata.thumb_csv.enabled = True
        self.config.sort.metadata.thumb_csv.auto_add = True
        self.config.locations.thumb_csv = str(path)
        aggregator = DataAggregator(self.config)

        aggregator.merge(
            [
                MovieData(
                    id="ABP-420",
                    actresses=[
                        Actress(last_name="Kamiki", first_name="Rei"),
                        Actress(last_name="Kamiki", first_name="Rei"),
                    ],
                    source="test",
                )
            ]
        )

        rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
        assert len(rows) == 1
