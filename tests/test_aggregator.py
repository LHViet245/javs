"""Tests for data aggregator."""

import csv
from unittest.mock import Mock

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
        assert identity.display_full_name == "Kamiki Rei"
        assert identity.display_japanese_name == "神木麗"
        assert identity.match_keys == {
            "jp:神木麗",
            "en:kamiki_rei",
            "en:rei_kamiki",
            "jp:別名",
        }

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

    def test_thumb_csv_reordered_multi_token_legacy_row_matches(self, tmp_path):
        path = tmp_path / "thumbs.csv"
        path.write_text(
            "FullName,JapaneseName,ThumbUrl\n"
            "Anna Marie Smith,,https://example.com/multi-token.jpg\n",
            encoding="utf-8",
        )
        self.config.sort.metadata.thumb_csv.enabled = True
        self.config.locations.thumb_csv = str(path)
        aggregator = DataAggregator(self.config)

        result = aggregator.merge(
            [
                MovieData(
                    id="ABP-420",
                    actresses=[Actress(last_name="Smith", first_name="Anna Marie")],
                    source="test",
                )
            ]
        )

        assert result.actresses[0].thumb_url == "https://example.com/multi-token.jpg"

    def test_thumb_csv_legacy_english_only_row_upgrades_to_japanese_canonical(self, tmp_path):
        path = tmp_path / "thumbs.csv"
        path.write_text(
            "FullName,JapaneseName,ThumbUrl\n"
            "Kamiki Rei,,https://example.com/legacy.jpg\n",
            encoding="utf-8",
        )
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
                        )
                    ],
                    source="test",
                )
            ]
        )

        rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
        assert rows == [
            {
                "CanonicalKey": "jp:神木麗",
                "FullName": "Kamiki Rei",
                "JapaneseName": "神木麗",
                "ThumbUrl": "https://example.com/legacy.jpg",
                "Aliases": "en:kamiki_rei|en:rei_kamiki",
            }
        ]

    def test_thumb_csv_alias_based_merge_instead_of_append(self, tmp_path):
        path = tmp_path / "thumbs.csv"
        path.write_text(
            "CanonicalKey,FullName,JapaneseName,ThumbUrl,Aliases\n"
            "jp:演員a,,演員A,,en:alias_performer\n",
            encoding="utf-8",
        )
        self.config.sort.metadata.thumb_csv.enabled = True
        self.config.sort.metadata.thumb_csv.convert_alias = True
        self.config.sort.metadata.thumb_csv.auto_add = True
        self.config.locations.thumb_csv = str(path)
        aggregator = DataAggregator(self.config)

        aggregator.merge(
            [
                MovieData(
                    id="ABP-420",
                    actresses=[
                        Actress(
                            japanese_name="演員A",
                            english_aliases=[
                                ActressAlias(last_name="Alias", first_name="Performer")
                            ],
                            thumb_url="https://example.com/alias.jpg",
                        )
                    ],
                    source="test",
                )
            ]
        )

        rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
        assert rows == [
            {
                "CanonicalKey": "jp:演員a",
                "FullName": "",
                "JapaneseName": "演員A",
                "ThumbUrl": "https://example.com/alias.jpg",
                "Aliases": "en:alias_performer|en:performer_alias",
            }
        ]

    def test_thumb_csv_unprefixed_english_aliases_on_japanese_row_stay_english(self, tmp_path):
        path = tmp_path / "thumbs.csv"
        path.write_text(
            "CanonicalKey,FullName,JapaneseName,ThumbUrl,Aliases\n"
            "jp:神木麗,,神木麗,,Kamiki Rei|Rei Kamiki\n",
            encoding="utf-8",
        )
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
                "CanonicalKey": "jp:神木麗",
                "FullName": "Kamiki Rei",
                "JapaneseName": "神木麗",
                "ThumbUrl": "https://example.com/rei.jpg",
                "Aliases": "en:kamiki_rei|en:rei_kamiki",
            }
        ]

    def test_thumb_csv_unprefixed_english_aliases_on_japanese_row_resolve_lookup(
        self, tmp_path
    ):
        path = tmp_path / "thumbs.csv"
        path.write_text(
            "CanonicalKey,FullName,JapaneseName,ThumbUrl,Aliases\n"
            "jp:神木麗,,神木麗,https://example.com/rei.jpg,Kamiki Rei|Rei Kamiki\n",
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

        assert result.actresses[0].thumb_url == "https://example.com/rei.jpg"

    def test_thumb_csv_conflicting_thumb_url_preserved(self, tmp_path):
        path = tmp_path / "thumbs.csv"
        path.write_text(
            "CanonicalKey,FullName,JapaneseName,ThumbUrl,Aliases\n"
            "jp:神木麗,Kamiki Rei,神木麗,https://example.com/cached.jpg,en:kamiki_rei|en:rei_kamiki\n",
            encoding="utf-8",
        )
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
                            thumb_url="https://example.com/scraper.jpg",
                        )
                    ],
                    source="test",
                )
            ]
        )

        rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
        assert rows == [
            {
                "CanonicalKey": "jp:神木麗",
                "FullName": "Kamiki Rei",
                "JapaneseName": "神木麗",
                "ThumbUrl": "https://example.com/cached.jpg",
                "Aliases": "en:kamiki_rei|en:rei_kamiki",
            }
        ]

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

    def test_thumb_csv_lookup_prefers_japanese_canonical_row_over_alias_match(self, tmp_path):
        path = tmp_path / "thumbs.csv"
        path.write_text(
            "CanonicalKey,FullName,JapaneseName,ThumbUrl,Aliases\n"
            "en:alias_performer,Alias Performer,,https://example.com/alias.jpg,en:performer_alias\n"
            "jp:演員a,,演員A,https://example.com/japanese.jpg,en:alias_performer|en:performer_alias\n",
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

        assert result.actresses[0].thumb_url == "https://example.com/japanese.jpg"

    def test_thumb_csv_lookup_prefers_larger_overlap_after_rank_and_strength(self, tmp_path):
        path = tmp_path / "thumbs.csv"
        path.write_text(
            "CanonicalKey,FullName,JapaneseName,ThumbUrl,Aliases\n"
            "en:alias_performer,,,https://example.com/minimal.jpg,\n"
            "en:alias_performer,Alias Performer,,https://example.com/overlap.jpg,\n",
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

        assert result.actresses[0].thumb_url == "https://example.com/overlap.jpg"

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
                "CanonicalKey": "jp:神木麗",
                "FullName": "Kamiki Rei",
                "JapaneseName": "神木麗",
                "ThumbUrl": "https://example.com/rei.jpg",
                "Aliases": "en:kamiki_rei|en:rei_kamiki",
            }
        ]

    def test_thumb_csv_auto_add_uses_append_for_brand_new_row(self, tmp_path, monkeypatch):
        path = tmp_path / "thumbs.csv"
        self.config.sort.metadata.thumb_csv.enabled = True
        self.config.sort.metadata.thumb_csv.auto_add = True
        self.config.locations.thumb_csv = str(path)
        aggregator = DataAggregator(self.config)

        append_calls: list[tuple[str, list[str], list[dict[str, str]]]] = []
        rewrite_calls: list[list[dict[str, str]]] = []
        original_append = aggregator._append_csv_rows
        original_write = aggregator._write_thumb_rows

        def spy_append(
            filename: str,
            fieldnames: list[str],
            rows: list[dict[str, str]],
        ) -> None:
            append_calls.append(
                (
                    filename,
                    list(fieldnames),
                    [dict(row) for row in rows],
                )
            )
            return original_append(filename, fieldnames, rows)

        def spy_write(rows: list[dict[str, str]]) -> None:
            rewrite_calls.append([dict(row) for row in rows])
            return original_write(rows)

        monkeypatch.setattr(aggregator, "_append_csv_rows", spy_append)
        monkeypatch.setattr(aggregator, "_write_thumb_rows", spy_write)

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

        assert append_calls == [
            (
                "thumbs.csv",
                ["CanonicalKey", "FullName", "JapaneseName", "ThumbUrl", "Aliases"],
                [
                    {
                        "CanonicalKey": "jp:神木麗",
                        "FullName": "Kamiki Rei",
                        "JapaneseName": "神木麗",
                        "ThumbUrl": "https://example.com/rei.jpg",
                        "Aliases": "en:kamiki_rei|en:rei_kamiki",
                    }
                ],
            )
        ]
        assert rewrite_calls == []

    def test_thumb_csv_auto_add_rewrites_legacy_file_before_appending_new_row(
        self, tmp_path, monkeypatch
    ):
        path = tmp_path / "thumbs.csv"
        path.write_text(
            "FullName,JapaneseName,ThumbUrl\n"
            "Doe Jane,,https://example.com/jane.jpg\n",
            encoding="utf-8",
        )
        self.config.sort.metadata.thumb_csv.enabled = True
        self.config.sort.metadata.thumb_csv.auto_add = True
        self.config.locations.thumb_csv = str(path)
        aggregator = DataAggregator(self.config)

        append_calls: list[tuple[str, list[str], list[dict[str, str]]]] = []
        rewrite_calls: list[list[dict[str, str]]] = []
        original_append = aggregator._append_csv_rows
        original_write = aggregator._write_thumb_rows

        def spy_append(
            filename: str,
            fieldnames: list[str],
            rows: list[dict[str, str]],
        ) -> None:
            append_calls.append(
                (
                    filename,
                    list(fieldnames),
                    [dict(row) for row in rows],
                )
            )
            return original_append(filename, fieldnames, rows)

        def spy_write(rows: list[dict[str, str]]) -> None:
            rewrite_calls.append([dict(row) for row in rows])
            return original_write(rows)

        monkeypatch.setattr(aggregator, "_append_csv_rows", spy_append)
        monkeypatch.setattr(aggregator, "_write_thumb_rows", spy_write)

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

        assert append_calls == []
        assert rewrite_calls == [
            [
                {
                    "CanonicalKey": "en:doe_jane",
                    "FullName": "Doe Jane",
                    "JapaneseName": "",
                    "ThumbUrl": "https://example.com/jane.jpg",
                    "Aliases": "en:jane_doe",
                },
                {
                    "CanonicalKey": "jp:神木麗",
                    "FullName": "Kamiki Rei",
                    "JapaneseName": "神木麗",
                    "ThumbUrl": "https://example.com/rei.jpg",
                    "Aliases": "en:kamiki_rei|en:rei_kamiki",
                },
            ]
        ]

    def test_thumb_csv_multi_token_legacy_row_rewrites_with_reordered_alias(self, tmp_path):
        path = tmp_path / "thumbs.csv"
        path.write_text(
            "FullName,JapaneseName,ThumbUrl\n"
            "Anna Marie Smith,,https://example.com/multi-token.jpg\n",
            encoding="utf-8",
        )
        self.config.sort.metadata.thumb_csv.enabled = True
        self.config.sort.metadata.thumb_csv.auto_add = True
        self.config.locations.thumb_csv = str(path)
        aggregator = DataAggregator(self.config)

        aggregator.merge(
            [
                MovieData(
                    id="ABP-420",
                    actresses=[Actress(last_name="Smith", first_name="Anna Marie")],
                    source="test",
                )
            ]
        )

        rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
        assert rows == [
            {
                "CanonicalKey": "en:anna_marie_smith",
                "FullName": "Anna Marie Smith",
                "JapaneseName": "",
                "ThumbUrl": "https://example.com/multi-token.jpg",
                "Aliases": "en:smith_anna_marie",
            }
        ]

    def test_thumb_csv_merge_uses_atomic_rewrite_for_existing_row(self, tmp_path, monkeypatch):
        path = tmp_path / "thumbs.csv"
        path.write_text(
            "CanonicalKey,FullName,JapaneseName,ThumbUrl,Aliases\n"
            "en:kamiki_rei,Kamiki Rei,,https://example.com/legacy.jpg,\n",
            encoding="utf-8",
        )
        self.config.sort.metadata.thumb_csv.enabled = True
        self.config.sort.metadata.thumb_csv.auto_add = True
        self.config.locations.thumb_csv = str(path)
        aggregator = DataAggregator(self.config)

        append_calls: list[tuple[str, list[str], list[dict[str, str]]]] = []
        rewrite_calls: list[list[dict[str, str]]] = []
        original_append = aggregator._append_csv_rows
        original_write = aggregator._write_thumb_rows

        def spy_append(
            filename: str,
            fieldnames: list[str],
            rows: list[dict[str, str]],
        ) -> None:
            append_calls.append(
                (
                    filename,
                    list(fieldnames),
                    [dict(row) for row in rows],
                )
            )
            return original_append(filename, fieldnames, rows)

        def spy_write(rows: list[dict[str, str]]) -> None:
            rewrite_calls.append([dict(row) for row in rows])
            return original_write(rows)

        monkeypatch.setattr(aggregator, "_append_csv_rows", spy_append)
        monkeypatch.setattr(aggregator, "_write_thumb_rows", spy_write)

        aggregator.merge(
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

        assert append_calls == []
        assert rewrite_calls == [
            [
                {
                    "CanonicalKey": "jp:神木麗",
                    "FullName": "Kamiki Rei",
                    "JapaneseName": "神木麗",
                    "ThumbUrl": "https://example.com/legacy.jpg",
                    "Aliases": "en:kamiki_rei|en:rei_kamiki",
                }
            ]
        ]

    def test_thumb_csv_mixed_merge_and_append_rewrites_entire_batch(self, tmp_path, monkeypatch):
        path = tmp_path / "thumbs.csv"
        path.write_text(
            "CanonicalKey,FullName,JapaneseName,ThumbUrl,Aliases\n"
            "en:kamiki_rei,Kamiki Rei,,https://example.com/legacy.jpg,\n",
            encoding="utf-8",
        )
        self.config.sort.metadata.thumb_csv.enabled = True
        self.config.sort.metadata.thumb_csv.auto_add = True
        self.config.locations.thumb_csv = str(path)
        aggregator = DataAggregator(self.config)

        append_calls: list[tuple[str, list[str], list[dict[str, str]]]] = []
        rewrite_calls: list[list[dict[str, str]]] = []
        original_append = aggregator._append_csv_rows
        original_write = aggregator._write_thumb_rows

        def spy_append(
            filename: str,
            fieldnames: list[str],
            rows: list[dict[str, str]],
        ) -> None:
            append_calls.append(
                (
                    filename,
                    list(fieldnames),
                    [dict(row) for row in rows],
                )
            )
            return original_append(filename, fieldnames, rows)

        def spy_write(rows: list[dict[str, str]]) -> None:
            rewrite_calls.append([dict(row) for row in rows])
            return original_write(rows)

        monkeypatch.setattr(aggregator, "_append_csv_rows", spy_append)
        monkeypatch.setattr(aggregator, "_write_thumb_rows", spy_write)

        aggregator.merge(
            [
                MovieData(
                    id="ABP-420",
                    actresses=[
                        Actress(
                            last_name="Kamiki",
                            first_name="Rei",
                            japanese_name="神木麗",
                        ),
                        Actress(
                            last_name="Doe",
                            first_name="Jane",
                            thumb_url="https://example.com/jane.jpg",
                        ),
                    ],
                    source="test",
                )
            ]
        )

        assert append_calls == []
        assert rewrite_calls == [
            [
                {
                    "CanonicalKey": "jp:神木麗",
                    "FullName": "Kamiki Rei",
                    "JapaneseName": "神木麗",
                    "ThumbUrl": "https://example.com/legacy.jpg",
                    "Aliases": "en:kamiki_rei|en:rei_kamiki",
                },
                {
                    "CanonicalKey": "en:doe_jane",
                    "FullName": "Doe Jane",
                    "JapaneseName": "",
                    "ThumbUrl": "https://example.com/jane.jpg",
                    "Aliases": "en:jane_doe",
                },
            ]
        ]

    def test_thumb_csv_mixed_merge_and_append_persists_both_updates(self, tmp_path):
        path = tmp_path / "thumbs.csv"
        path.write_text(
            "CanonicalKey,FullName,JapaneseName,ThumbUrl,Aliases\n"
            "en:kamiki_rei,Kamiki Rei,,https://example.com/legacy.jpg,\n",
            encoding="utf-8",
        )
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
                        ),
                        Actress(
                            last_name="Doe",
                            first_name="Jane",
                            thumb_url="https://example.com/jane.jpg",
                        ),
                        Actress(
                            last_name="Jane",
                            first_name="Doe",
                            thumb_url="https://example.com/jane-ignored.jpg",
                        ),
                    ],
                    source="test",
                )
            ]
        )

        rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
        assert rows == [
            {
                "CanonicalKey": "jp:神木麗",
                "FullName": "Kamiki Rei",
                "JapaneseName": "神木麗",
                "ThumbUrl": "https://example.com/legacy.jpg",
                "Aliases": "en:kamiki_rei|en:rei_kamiki",
            },
            {
                "CanonicalKey": "en:doe_jane",
                "FullName": "Doe Jane",
                "JapaneseName": "",
                "ThumbUrl": "https://example.com/jane.jpg",
                "Aliases": "en:jane_doe",
            },
        ]

    def test_thumb_csv_append_failure_reloads_state_from_disk(self, tmp_path, monkeypatch):
        path = tmp_path / "thumbs.csv"
        self.config.sort.metadata.thumb_csv.enabled = True
        self.config.sort.metadata.thumb_csv.auto_add = True
        self.config.locations.thumb_csv = str(path)
        aggregator = DataAggregator(self.config)

        def fail_append(
            filename: str,
            fieldnames: list[str],
            rows: list[dict[str, str]],
        ) -> bool:
            return False

        monkeypatch.setattr(aggregator, "_append_csv_rows", fail_append)

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

        assert not path.exists()
        assert aggregator._thumb_rows == []
        assert aggregator._thumb_known_names == set()

    def test_thumb_csv_rewrite_failure_reloads_state_from_disk(self, tmp_path, monkeypatch):
        path = tmp_path / "thumbs.csv"
        path.write_text(
            "CanonicalKey,FullName,JapaneseName,ThumbUrl,Aliases\n"
            "en:kamiki_rei,Kamiki Rei,,https://example.com/legacy.jpg,\n",
            encoding="utf-8",
        )
        self.config.sort.metadata.thumb_csv.enabled = True
        self.config.sort.metadata.thumb_csv.auto_add = True
        self.config.locations.thumb_csv = str(path)
        aggregator = DataAggregator(self.config)

        def fail_write(rows: list[dict[str, str]]) -> bool:
            return False

        monkeypatch.setattr(aggregator, "_write_thumb_rows", fail_write)

        aggregator.merge(
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

        rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
        assert rows == [
            {
                "CanonicalKey": "en:kamiki_rei",
                "FullName": "Kamiki Rei",
                "JapaneseName": "",
                "ThumbUrl": "https://example.com/legacy.jpg",
                "Aliases": "",
            }
        ]
        assert aggregator._thumb_rows == [
            {
                "CanonicalKey": "en:kamiki_rei",
                "FullName": "Kamiki Rei",
                "JapaneseName": "",
                "ThumbUrl": "https://example.com/legacy.jpg",
                "Aliases": "en:rei_kamiki",
            }
        ]

    def test_thumb_csv_lookup_prefers_direct_name_match_over_alias_only_match(self, tmp_path):
        path = tmp_path / "thumbs.csv"
        path.write_text(
            "CanonicalKey,FullName,JapaneseName,ThumbUrl,Aliases\n"
            "en:performer_alias,Performer Alias,,https://example.com/direct.jpg,\n"
            "jp:別名,,別名,https://example.com/alias.jpg,en:alias_performer\n",
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
                            last_name="Alias",
                            first_name="Performer",
                            japanese_aliases=[JapaneseAlias(japanese_name="別名")],
                        )
                    ],
                    source="test",
                )
            ]
        )

        assert result.actresses[0].thumb_url == "https://example.com/direct.jpg"

    def test_thumb_csv_lookup_prefers_more_specific_alias_only_match(self, tmp_path):
        path = tmp_path / "thumbs.csv"
        path.write_text(
            "CanonicalKey,FullName,JapaneseName,ThumbUrl,Aliases\n"
            "jp:別名,,別名,https://example.com/jp.jpg,en:alias_performer\n"
            "en:alias_performer,Alias Performer,,https://example.com/en.jpg,en:performer_alias\n",
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

        assert result.actresses[0].thumb_url == "https://example.com/en.jpg"

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

    def test_thumb_csv_preserved_thumb_conflict_logs_warning(self, tmp_path, monkeypatch):
        path = tmp_path / "thumbs.csv"
        path.write_text(
            "CanonicalKey,FullName,JapaneseName,ThumbUrl,Aliases\n"
            "jp:神木麗,Kamiki Rei,神木麗,https://example.com/cached.jpg,en:kamiki_rei|en:rei_kamiki\n",
            encoding="utf-8",
        )
        self.config.sort.metadata.thumb_csv.enabled = True
        self.config.sort.metadata.thumb_csv.auto_add = True
        self.config.locations.thumb_csv = str(path)
        aggregator = DataAggregator(self.config)

        warning = Mock()
        monkeypatch.setattr("javs.core.aggregator.logger.warning", warning)

        aggregator.merge(
            [
                MovieData(
                    id="ABP-420",
                    actresses=[
                        Actress(
                            last_name="Kamiki",
                            first_name="Rei",
                            japanese_name="神木麗",
                            thumb_url="https://example.com/scraper.jpg",
                        )
                    ],
                    source="test",
                )
            ]
        )

        warning.assert_any_call(
            "thumb_csv_thumb_conflict_preserved",
            existing_thumb_url="https://example.com/cached.jpg",
            incoming_thumb_url="https://example.com/scraper.jpg",
            canonical_key="jp:神木麗",
        )

    def test_thumb_csv_preserved_name_conflicts_log_warning(self, tmp_path, monkeypatch):
        path = tmp_path / "thumbs.csv"
        path.write_text(
            "CanonicalKey,FullName,JapaneseName,ThumbUrl,Aliases\n"
            "jp:神木麗,Stored Name,保存名,https://example.com/cached.jpg,\n",
            encoding="utf-8",
        )
        self.config.sort.metadata.thumb_csv.enabled = True
        self.config.sort.metadata.thumb_csv.auto_add = True
        self.config.locations.thumb_csv = str(path)
        aggregator = DataAggregator(self.config)

        warning = Mock()
        monkeypatch.setattr("javs.core.aggregator.logger.warning", warning)

        aggregator.merge(
            [
                MovieData(
                    id="ABP-420",
                    actresses=[
                        Actress(
                            last_name="Incoming",
                            first_name="Name",
                            japanese_name="神木麗",
                        )
                    ],
                    source="test",
                )
            ]
        )

        warning.assert_any_call(
            "thumb_csv_name_conflict_preserved",
            field="FullName",
            existing_value="Stored Name",
            incoming_value="Incoming Name",
            canonical_key="jp:神木麗",
        )
        warning.assert_any_call(
            "thumb_csv_name_conflict_preserved",
            field="JapaneseName",
            existing_value="保存名",
            incoming_value="神木麗",
            canonical_key="jp:神木麗",
        )
