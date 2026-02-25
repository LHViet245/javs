"""Tests for R18Dev scraper with mocked API responses."""

from datetime import date

from javs.models.movie import MovieData
from javs.scrapers.r18dev import R18DevScraper

# ─── Sample API response fixtures ──────────────────────────

SAMPLE_SEARCH_RESPONSE = {
    "dvd_id": "ABP-420",
    "content_id": "118abp00420",
    "title": "ABP-420 Test Movie",
}

SAMPLE_DETAIL_RESPONSE = {
    "dvd_id": "ABP-420",
    "content_id": "118abp00420",
    "title": "ABP-420 Test Movie",
    "title_en": "Prestige Exclusive - Beautiful Girl",
    "title_ja": "プレステージ専属 美少女",
    "comment_en": "A test description for this movie.",
    "release_date": "2023-06-15 10:00:00",
    "runtime_mins": 120,
    "directors": [{"name_romaji": "Test Director", "name_kanji": "テスト監督"}],
    "maker_name_en": "Prestige",
    "maker_name_ja": "プレステージ",
    "label_name_en": "ABSOLUTE PERFECT GIRL",
    "label_name_ja": "プレステージ",
    "series_name_en": "Exclusive Series",
    "series_name_ja": "専属シリーズ",
    "categories": [
        {"name_en": "Drama", "name_ja": "ドラマ"},
        {"name_en": "Beautiful Girl", "name_ja": "美少女"},
        {"name_en": "Prestige Exclusive", "name_ja": "プレステージ"},
    ],
    "actresses": [
        {
            "name_romaji": "Koharu Suzuki",
            "name_kanji": "鈴木心春",
            "image_url": "suzuki_koharu.jpg",
        },
        {
            "name_romaji": "Aika Yamagishi",
            "name_kanji": "山岸あいか（藍花）",
            "image_url": "https://pics.dmm.co.jp/mono/actjpgs/yamagishi_aika.jpg",
        },
    ],
    "jacket_full_url": "https://pics.dmm.co.jp/mono/movie/adult/118abp00420/118abp00420ps.jpg",
    "gallery": {
        "image_full": [
            "https://pics.dmm.co.jp/digital/video/118abp00420/118abp00420-1.jpg",
            "https://pics.dmm.co.jp/digital/video/118abp00420/118abp00420-2.jpg",
        ],
        "image_thumb": [
            "https://pics.dmm.co.jp/digital/video/118abp00420/118abp00420-1s.jpg",
        ],
    },
    "sample_url": "https://cc3001.dmm.co.jp/litevideo/freepv/1/118/118abp00420/118abp00420_dmb_w.mp4",
}


class TestR18DevScraper:
    """Test R18DevScraper field parsing with mock data."""

    def setup_method(self):
        self.scraper = R18DevScraper.__new__(R18DevScraper)
        from javs.utils.logging import get_logger

        self.scraper.logger = get_logger("test.r18dev")

    def test_parse_json_basic_fields(self):
        """Should extract all basic fields from JSON."""
        result = self.scraper._parse_json(SAMPLE_DETAIL_RESPONSE)

        assert isinstance(result, MovieData)
        assert result.id == "ABP-420"
        assert result.content_id == "118abp00420"
        assert result.source == "r18dev"

    def test_parse_title(self):
        """Should prefer title_en over generic title."""
        result = self.scraper._parse_json(SAMPLE_DETAIL_RESPONSE)
        assert result.title == "Prestige Exclusive - Beautiful Girl"

    def test_parse_title_fallback(self):
        """Should fall back to 'title' if title_en is missing."""
        data = {**SAMPLE_DETAIL_RESPONSE, "title_en": None}
        result = self.scraper._parse_json(data)
        assert result.title == "ABP-420 Test Movie"

    def test_parse_alternate_title_ja(self):
        """Should extract Japanese title."""
        result = self.scraper._parse_json(SAMPLE_DETAIL_RESPONSE)
        assert result.alternate_title == "プレステージ専属 美少女"

    def test_parse_description(self):
        """Should extract English description."""
        result = self.scraper._parse_json(SAMPLE_DETAIL_RESPONSE)
        assert result.description == "A test description for this movie."

    def test_parse_release_date(self):
        """Should parse release_date with time component."""
        result = self.scraper._parse_json(SAMPLE_DETAIL_RESPONSE)
        assert result.release_date == date(2023, 6, 15)

    def test_parse_release_date_none(self):
        """Missing release_date should be None."""
        data = {**SAMPLE_DETAIL_RESPONSE, "release_date": None}
        result = self.scraper._parse_json(data)
        assert result.release_date is None

    def test_parse_runtime(self):
        """Should extract runtime as int."""
        result = self.scraper._parse_json(SAMPLE_DETAIL_RESPONSE)
        assert result.runtime == 120

    def test_parse_director(self):
        """Should extract director romaji name."""
        result = self.scraper._parse_json(SAMPLE_DETAIL_RESPONSE)
        assert result.director == "Test Director"

    def test_parse_director_empty(self):
        """No directors should return None."""
        data = {**SAMPLE_DETAIL_RESPONSE, "directors": []}
        result = self.scraper._parse_json(data)
        assert result.director is None

    def test_parse_maker(self):
        result = self.scraper._parse_json(SAMPLE_DETAIL_RESPONSE)
        assert result.maker == "Prestige"

    def test_parse_label(self):
        result = self.scraper._parse_json(SAMPLE_DETAIL_RESPONSE)
        assert result.label == "ABSOLUTE PERFECT GIRL"

    def test_parse_series(self):
        result = self.scraper._parse_json(SAMPLE_DETAIL_RESPONSE)
        assert result.series == "Exclusive Series"

    def test_parse_genres(self):
        result = self.scraper._parse_json(SAMPLE_DETAIL_RESPONSE)
        assert "Drama" in result.genres
        assert "Beautiful Girl" in result.genres
        assert "Prestige Exclusive" in result.genres

    def test_parse_genres_empty(self):
        data = {**SAMPLE_DETAIL_RESPONSE, "categories": []}
        result = self.scraper._parse_json(data)
        assert result.genres == []

    # ─── Actress Tests ──────────────────────────────────────

    def test_parse_actresses_count(self):
        result = self.scraper._parse_json(SAMPLE_DETAIL_RESPONSE)
        assert len(result.actresses) == 2

    def test_parse_actress_name_split(self):
        """Romaji 'FirstName LastName' should be split correctly."""
        result = self.scraper._parse_json(SAMPLE_DETAIL_RESPONSE)
        actress = result.actresses[0]
        assert actress.first_name == "Koharu"
        assert actress.last_name == "Suzuki"

    def test_parse_actress_japanese_name(self):
        result = self.scraper._parse_json(SAMPLE_DETAIL_RESPONSE)
        assert result.actresses[0].japanese_name == "鈴木心春"

    def test_parse_actress_japanese_name_cleaned(self):
        """Aliases in （） should be removed."""
        result = self.scraper._parse_json(SAMPLE_DETAIL_RESPONSE)
        assert result.actresses[1].japanese_name == "山岸あいか"

    def test_parse_actress_thumb_url_relative(self):
        """Relative image_url should get DMM prefix."""
        result = self.scraper._parse_json(SAMPLE_DETAIL_RESPONSE)
        thumb = result.actresses[0].thumb_url
        assert thumb == "https://pics.dmm.co.jp/mono/actjpgs/suzuki_koharu.jpg"

    def test_parse_actress_thumb_url_absolute(self):
        """Absolute image_url should be kept as-is."""
        result = self.scraper._parse_json(SAMPLE_DETAIL_RESPONSE)
        thumb = result.actresses[1].thumb_url
        assert thumb == "https://pics.dmm.co.jp/mono/actjpgs/yamagishi_aika.jpg"

    def test_parse_actresses_empty(self):
        data = {**SAMPLE_DETAIL_RESPONSE, "actresses": None}
        result = self.scraper._parse_json(data)
        assert result.actresses == []

    # ─── Media URL Tests ────────────────────────────────────

    def test_parse_cover_url(self):
        """Cover URL should replace ps.jpg with pl.jpg."""
        result = self.scraper._parse_json(SAMPLE_DETAIL_RESPONSE)
        assert result.cover_url is not None
        assert "pl.jpg" in result.cover_url
        assert "ps.jpg" not in result.cover_url

    def test_parse_screenshot_urls(self):
        result = self.scraper._parse_json(SAMPLE_DETAIL_RESPONSE)
        assert len(result.screenshot_urls) == 2

    def test_parse_screenshot_urls_fallback_to_thumb(self):
        data = {
            **SAMPLE_DETAIL_RESPONSE,
            "gallery": {
                "image_full": None,
                "image_thumb": ["https://example.com/thumb-1.jpg"],
            },
        }
        result = self.scraper._parse_json(data)
        assert len(result.screenshot_urls) == 1

    def test_parse_trailer_url(self):
        result = self.scraper._parse_json(SAMPLE_DETAIL_RESPONSE)
        assert result.trailer_url is not None
        assert "dmb_w.mp4" in result.trailer_url

    def test_parse_trailer_url_none(self):
        data = {**SAMPLE_DETAIL_RESPONSE, "sample_url": None}
        result = self.scraper._parse_json(data)
        assert result.trailer_url is None

    # ─── Edge Cases ─────────────────────────────────────────

    def test_parse_minimal_json(self):
        data = {"dvd_id": "TEST-001"}
        result = self.scraper._parse_json(data)
        assert result.id == "TEST-001"
        assert result.title is None
        assert result.actresses == []
        assert result.genres == []

    def test_parse_empty_json(self):
        result = self.scraper._parse_json({})
        assert result.id == ""
        assert result.source == "r18dev"
