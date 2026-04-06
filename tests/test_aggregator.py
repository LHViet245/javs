"""Tests for data aggregator."""

import csv

from javs.config import JavsConfig
from javs.core.aggregator import DataAggregator
from javs.models.movie import Actress, ActressAlias, JapaneseAlias, MovieData, Rating


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

    def test_merge_preserves_cover_and_trailer_source(self):
        """Merged asset fields should remember which scraper supplied them."""
        data1 = MovieData(
            id="ABP-420",
            source="dmm",
            cover_url="https://dmm.example/cover.jpg",
        )
        data2 = MovieData(
            id="ABP-420",
            source="r18dev",
            trailer_url="https://r18.example/trailer.mp4",
        )

        result = self.aggregator.merge([data1, data2])

        assert result.cover_source == "dmm"
        assert result.trailer_source == "r18dev"
        assert result.field_sources["cover_url"] == "dmm"
        assert result.field_sources["trailer_url"] == "r18dev"

    def test_merge_preserves_screenshot_source(self):
        """Merged screenshot URLs should remember which scraper supplied them."""
        self.config.sort.metadata.priority.screenshot_url = ["dmm", "r18dev"]
        self.aggregator = DataAggregator(self.config)
        data1 = MovieData(
            id="ABP-420",
            source="dmm",
            screenshot_urls=["https://dmm.example/1.jpg"],
        )
        data2 = MovieData(
            id="ABP-420",
            source="r18dev",
            screenshot_urls=["https://r18.example/1.jpg"],
        )

        result = self.aggregator.merge([data1, data2])

        assert result.screenshot_source == "dmm"
        assert result.field_sources["screenshot_urls"] == "dmm"

    def test_single_source_asset_source_overrides_general_source(self):
        """Single-source asset provenance should stay aligned with the asset source field."""
        data = MovieData(
            id="ABP-420",
            title="Example",
            cover_url="https://example.com/cover.jpg",
            cover_source="r18dev",
            source="dmm",
        )

        result = self.aggregator.merge([data])

        assert result.cover_source == "r18dev"
        assert result.field_sources["cover_url"] == "r18dev"

    def test_single_source_populates_field_sources_from_source(self):
        """Single-source data should backfill field provenance from its scraper."""
        data = MovieData(
            id="ABP-420",
            title="Example",
            description="Plot",
            maker="IdeaPocket",
            rating=Rating(rating=9.1, votes=120),
            genres=["Drama"],
            actresses=[Actress(last_name="Doe", first_name="Jane")],
            source="dmm",
        )

        result = self.aggregator.merge([data])

        assert result.field_sources["title"] == "dmm"
        assert result.field_sources["description"] == "dmm"
        assert result.field_sources["maker"] == "dmm"
        assert result.field_sources["rating"] == "dmm"
        assert result.field_sources["genres"] == "dmm"
        assert result.field_sources["actresses"] == "dmm"

    def test_multi_source_populates_winning_scalar_field_sources(self):
        """Merged scalar fields should record the source that won each field."""
        self.config.sort.metadata.priority.title = ["dmm", "javlibrary"]
        self.config.sort.metadata.priority.maker = ["dmm", "javlibrary"]
        self.aggregator = DataAggregator(self.config)
        data1 = MovieData(
            id="ABP-420",
            title="Winner Title",
            description="Winner Description",
            maker="Winner Studio",
            rating=Rating(rating=9.2, votes=80),
            source="dmm",
        )
        data2 = MovieData(
            id="ABP-420",
            title="Loser Title",
            description="Loser Description",
            maker="Loser Studio",
            rating=Rating(rating=6.5, votes=12),
            source="javlibrary",
        )

        result = self.aggregator.merge([data1, data2])

        assert result.title == "Winner Title"
        assert result.description == "Winner Description"
        assert result.maker == "Winner Studio"
        assert result.rating == Rating(rating=9.2, votes=80)
        assert result.field_sources["title"] == "dmm"
        assert result.field_sources["description"] == "dmm"
        assert result.field_sources["maker"] == "dmm"
        assert result.field_sources["rating"] == "dmm"

    def test_movie_data_preserves_field_sources_and_asset_sources(self):
        """MovieData should keep general provenance alongside asset source fields."""
        data = MovieData(
            id="ABP-420",
            title="Example",
            field_sources={"title": "dmm", "cover_url": "r18dev"},
            cover_source="dmm",
            trailer_source="r18dev",
            screenshot_source="mgstageja",
        )

        copied = data.model_copy(deep=True)
        copied.field_sources["title"] = "javlibrary"
        data.field_sources["cover_url"] = "dmm"

        assert copied.field_sources == {"title": "javlibrary", "cover_url": "r18dev"}
        assert data.field_sources == {"title": "dmm", "cover_url": "dmm"}
        assert copied.cover_source == "dmm"
        assert copied.trailer_source == "r18dev"
        assert copied.screenshot_source == "mgstageja"

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

    def test_thumb_identity_keys_prefer_japanese_canonical_key(self):
        actress = Actress(
            last_name="Ｋａｍｉｋｉ",
            first_name="  Ｒｅｉ  ",
            japanese_name="神木麗",
            english_aliases=[ActressAlias(last_name="Ｒｅｉ", first_name="Ｋａｍｉｋｉ")],
            japanese_aliases=[JapaneseAlias(japanese_name="別名")],
        )

        identity = self.aggregator._build_actress_identity(actress)

        assert identity.canonical_key == "jp:神木麗"
        assert identity.match_keys == (
            "jp:神木麗",
            "en:kamiki_rei",
            "en:rei_kamiki",
            "jp:別名",
        )

    def test_thumb_csv_reordered_legacy_row_matches(self, tmp_path):
        path = tmp_path / "thumbs.csv"
        path.write_text(
            "FullName,JapaneseName,ThumbUrl\n"
            "Rei Kamiki,,https://example.com/reordered.jpg\n",
            encoding="utf-8",
        )
        self.config.sort.metadata.thumb_csv.enabled = True
        self.config.locations.thumb_csv = str(path)
        aggregator = DataAggregator(self.config)

        result = aggregator.merge(
            [
                MovieData(
                    id="ABP-420",
                    actresses=[Actress(last_name="Kamiki", first_name="Rei")],
                    source="test",
                )
            ]
        )

        assert result.actresses[0].thumb_url == "https://example.com/reordered.jpg"

    def test_thumb_csv_legacy_english_only_row_uses_japanese_canonical_identity(self, tmp_path):
        path = tmp_path / "thumbs.csv"
        path.write_text(
            "FullName,JapaneseName,ThumbUrl\n"
            "Kamiki Rei,,https://example.com/legacy.jpg\n",
            encoding="utf-8",
        )
        self.config.sort.metadata.thumb_csv.enabled = True
        self.config.locations.thumb_csv = str(path)
        aggregator = DataAggregator(self.config)

        row_identity = aggregator._build_row_identity(
            {
                "FullName": "Kamiki Rei",
                "JapaneseName": "",
                "ThumbUrl": "https://example.com/legacy.jpg",
            }
        )
        actress_identity = aggregator._build_actress_identity(
            Actress(last_name="Kamiki", first_name="Rei", japanese_name="神木麗")
        )

        assert row_identity.canonical_key == "en:kamiki_rei"
        assert row_identity.match_keys == ("en:kamiki_rei", "en:rei_kamiki")
        assert actress_identity.canonical_key == "jp:神木麗"

        result = aggregator.merge(
            [
                MovieData(
                    id="ABP-420",
                    actresses=[
                        Actress(
                            last_name="Kamiki",
                            first_name="Rei",
                            japanese_name="神木麗",
                        )
                    ],
                    source="test",
                )
            ]
        )

        assert result.actresses[0].thumb_url == "https://example.com/legacy.jpg"

    def test_thumb_csv_alias_based_merge_instead_of_append(self, tmp_path):
        path = tmp_path / "thumbs.csv"
        path.write_text(
            "CanonicalKey,Aliases,ThumbUrl\n"
            "jp:神木麗,en:kamiki_rei|en:rei_kamiki,https://example.com/alias-match.jpg\n",
            encoding="utf-8",
        )
        self.config.sort.metadata.thumb_csv.enabled = True
        self.config.sort.metadata.thumb_csv.convert_alias = False
        self.config.sort.metadata.thumb_csv.auto_add = True
        self.config.locations.thumb_csv = str(path)
        aggregator = DataAggregator(self.config)

        result = aggregator.merge(
            [
                MovieData(
                    id="ABP-420",
                    actresses=[Actress(last_name="Kamiki", first_name="Rei")],
                    source="test",
                )
            ]
        )

        rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
        assert result.actresses[0].thumb_url == "https://example.com/alias-match.jpg"
        assert len(rows) == 1

    def test_thumb_csv_conflicting_thumb_url_preserved(self, tmp_path):
        path = tmp_path / "thumbs.csv"
        path.write_text(
            "CanonicalKey,Aliases,ThumbUrl\n"
            "jp:神木麗,en:kamiki_rei|en:rei_kamiki,https://example.com/cached.jpg\n",
            encoding="utf-8",
        )
        self.config.sort.metadata.thumb_csv.enabled = True
        self.config.sort.metadata.thumb_csv.convert_alias = False
        self.config.sort.metadata.thumb_csv.auto_add = True
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

        rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
        assert result.actresses[0].thumb_url == "https://example.com/scraper.jpg"
        assert rows[0]["ThumbUrl"] == "https://example.com/cached.jpg"
        assert len(rows) == 1

    def test_thumb_csv_resolves_future_canonical_key_rows(self, tmp_path):
        path = tmp_path / "thumbs.csv"
        path.write_text(
            "CanonicalKey,Aliases,ThumbUrl\n"
            "jp:神木麗,en:kamiki rei|en:rei kamiki,https://example.com/rei.jpg\n",
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

    def test_thumb_csv_resolves_future_alias_rows(self, tmp_path):
        path = tmp_path / "thumbs.csv"
        path.write_text(
            "CanonicalKey,Aliases,ThumbUrl\n"
            "jp:別名,en:Alias Performer|en:Performer Alias,https://example.com/alias.jpg\n",
            encoding="utf-8",
        )
        self.config.sort.metadata.thumb_csv.enabled = True
        self.config.locations.thumb_csv = str(path)
        aggregator = DataAggregator(self.config)

        result = aggregator.merge(
            [
                MovieData(
                    id="ABP-420",
                    actresses=[Actress(last_name="Alias", first_name="Performer")],
                    source="test",
                )
            ]
        )

        assert result.actresses[0].thumb_url == "https://example.com/alias.jpg"

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
