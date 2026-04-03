"""Tests for Javlibrary scraper with mock HTML fixtures."""

from __future__ import annotations

from datetime import date

import pytest

from javs.models.movie import MovieData
from javs.scrapers.javlibrary import JavlibraryJaScraper, JavlibraryScraper, JavlibraryZhScraper
from javs.services.http import CloudflareBlockedError
from javs.utils.html import parse_html

# ─── Mock HTML detail page ──────────────────────────────────

SAMPLE_DETAIL_HTML = """
<html>
<head><title>ABP-420 Prestige Exclusive Beautiful Girl - JAVLibrary</title></head>
<body>
<div id="video_id" class="item">
  <table><tr><td class="header">ID:</td><td class="text">ABP-420</td></tr></table>
</div>

<div id="video_date" class="item">
  <table><tr><td class="header">Release Date:</td><td class="text">2023-06-15</td></tr></table>
</div>

<div id="video_length" class="item">
  <table><tr><td class="header">Length:</td><td class="text"><span class="text">120</span> min</td></tr></table>
</div>

<div id="video_director" class="item">
  <table><tr><td class="header">Director:</td><td class="text"><a href="vl_director.php?d=1" rel="tag">Test Director</a></td></tr></table>
</div>

<div id="video_maker" class="item">
  <table><tr><td class="header">Maker:</td><td class="text"><a href="vl_maker.php?m=1" rel="tag">Prestige</a></td></tr></table>
</div>

<div id="video_label" class="item">
  <table><tr><td class="header">Label:</td><td class="text"><a href="vl_label.php?l=1" rel="tag">ABSOLUTE PERFECT GIRL</a></td></tr></table>
</div>

<div id="video_review" class="item">
  <table><tr><td class="header">User Rating:</td><td class="text"><span class="score">(7.50)</span></td></tr></table>
</div>

<div id="video_genres" class="item">
  <table><tr><td class="header">Genre(s):</td><td class="text">
    <span class="genre"><a href="vl_genre.php?g=1" rel="category tag">Drama</a></span>
    <span class="genre"><a href="vl_genre.php?g=2" rel="category tag">Beautiful Girl</a></span>
    <span class="genre"><a href="vl_genre.php?g=3" rel="category tag">Prestige Exclusive</a></span>
  </td></tr></table>
</div>

<div id="video_cast" class="item">
  <table><tr><td class="header">Cast:</td><td class="text">
    <span class="star"><a href="vl_star.php?s=1" rel="tag">Suzuki Koharu</a>
      <span id="alias_1" class="alias">鈴木心春</span>
    </span>
    <span class="star"><a href="vl_star.php?s=2" rel="tag">Yamagishi Aika</a></span>
  </td></tr></table>
</div>

<img id="video_jacket_img" src="//pics.dmm.co.jp/mono/movie/adult/118abp00420/118abp00420pl.jpg">

<div class="previewthumbs" style="display:block; margin:10px auto;">
  <img src="//pics.dmm.co.jp/digital/video/118abp00420/118abp00420-1.jpg">
  <img src="//pics.dmm.co.jp/digital/video/118abp00420/118abp00420-2.jpg">
</div>
</body>
</html>
"""

SAMPLE_SEARCH_RESULTS_HTML = """
<html>
<head><title>Search Results - JAVLibrary</title></head>
<body>
<div class="videothumblist">
  <div class="videos">
    <div class="video">
      <a href="./?v=javme12345" title="ABP-420 Prestige Beautiful"><div class="id">ABP-420</div></a>
    </div>
    <div class="video">
      <a href="./?v=javme12346" title="ABP-420 Prestige Beautiful (Blu-ray Disc)"><div class="id">ABP-420</div></a>
    </div>
    <div class="video">
      <a href="./?v=javme99999" title="SSIS-001 Another Movie"><div class="id">SSIS-001</div></a>
    </div>
  </div>
</div>
</body>
</html>
"""

SAMPLE_EMPTY_DETAIL_HTML = """
<html>
<head><title>ABP-999 Unknown - JAVLibrary</title></head>
<body>
<div id="video_id" class="item">
  <table><tr><td class="header">ID:</td><td class="text">ABP-999</td></tr></table>
</div>
</body>
</html>
"""

SAMPLE_JAPANESE_ACTRESS_HTML = """
<html><body>
<div id="video_id" class="item">
  <table><tr><td class="header">ID:</td><td class="text">TEST-001</td></tr></table>
</div>
<div id="video_cast" class="item">
  <table><tr><td class="header">Cast:</td><td class="text">
    <span class="star"><a href="vl_star.php?s=1" rel="tag">鈴木心春</a></span>
  </td></tr></table>
</div>
</body></html>
"""

SAMPLE_DIRECT_MATCH_WITH_CANONICAL = """
<html>
<head>
  <title>ABP-420 Detail - JAVLibrary</title>
  <link rel="canonical" href="/en/?v=javme12345">
</head>
<body>
<div id="video_id" class="item">
  <table><tr><td class="header">ID:</td><td class="text">ABP-420</td></tr></table>
</div>
</body>
</html>
"""

SAMPLE_DIRECT_MATCH_WITHOUT_CANONICAL = """
<html>
<head><title>ABP-420 Detail - JAVLibrary</title></head>
<body>
<div id="video_id" class="item">
  <table><tr><td class="header">ID:</td><td class="text">ABP-420</td></tr></table>
</div>
</body>
</html>
"""


class _FakeHttpClient:
    def __init__(self, html: str) -> None:
        self.html = html
        self.calls: list[dict[str, object]] = []

    async def get_cf(self, url: str, use_proxy: bool = False) -> str:
        self.calls.append({"url": url, "use_proxy": use_proxy})
        return self.html


class _BlockedHttpClient:
    async def get_cf(self, url: str, use_proxy: bool = False) -> str:
        raise CloudflareBlockedError("blocked")


class TestJavlibraryScraper:
    """Test JavlibraryScraper field parsing."""

    def setup_method(self):
        self.scraper = JavlibraryScraper.__new__(JavlibraryScraper)
        from javs.utils.logging import get_logger

        self.scraper.logger = get_logger("test.javlibrary")

    def _scrape_html(self, html: str) -> MovieData:
        """Helper: parse HTML and run scrape logic inline."""
        soup = parse_html(html)
        video_id_div = soup.select_one("div#video_id")
        movie_id = self.scraper._extract_item_value(video_id_div) if video_id_div else ""

        return MovieData(
            id=movie_id or "",
            title=self.scraper._parse_title(soup),
            release_date=self.scraper._parse_release_date(soup),
            runtime=self.scraper._parse_runtime(soup),
            director=self.scraper._parse_director(soup),
            maker=self.scraper._parse_maker(soup),
            label=self.scraper._parse_label(soup),
            rating=self.scraper._parse_rating(soup),
            genres=self.scraper._parse_genres(soup),
            actresses=self.scraper._parse_actresses(soup),
            cover_url=self.scraper._parse_cover_url(soup),
            screenshot_urls=self.scraper._parse_screenshot_urls(soup),
            source="javlibrary",
        )

    # ─── Basic Fields ───────────────────────────────────────

    def test_parse_id(self):
        result = self._scrape_html(SAMPLE_DETAIL_HTML)
        assert result.id == "ABP-420"

    def test_parse_title(self):
        result = self._scrape_html(SAMPLE_DETAIL_HTML)
        assert result.title == "Prestige Exclusive Beautiful Girl"

    def test_parse_release_date(self):
        result = self._scrape_html(SAMPLE_DETAIL_HTML)
        assert result.release_date == date(2023, 6, 15)

    def test_parse_runtime(self):
        result = self._scrape_html(SAMPLE_DETAIL_HTML)
        assert result.runtime == 120

    def test_parse_director(self):
        result = self._scrape_html(SAMPLE_DETAIL_HTML)
        assert result.director == "Test Director"

    def test_parse_maker(self):
        result = self._scrape_html(SAMPLE_DETAIL_HTML)
        assert result.maker == "Prestige"

    def test_parse_label(self):
        result = self._scrape_html(SAMPLE_DETAIL_HTML)
        assert result.label == "ABSOLUTE PERFECT GIRL"

    # ─── Rating ─────────────────────────────────────────────

    def test_parse_rating(self):
        result = self._scrape_html(SAMPLE_DETAIL_HTML)
        assert result.rating is not None
        assert result.rating.rating == 7.50

    def test_parse_rating_zero(self):
        """Rating of 0 should be None."""
        html = SAMPLE_DETAIL_HTML.replace("(7.50)", "(0)")
        result = self._scrape_html(html)
        assert result.rating is None

    # ─── Genres ─────────────────────────────────────────────

    def test_parse_genres(self):
        result = self._scrape_html(SAMPLE_DETAIL_HTML)
        assert "Drama" in result.genres
        assert "Beautiful Girl" in result.genres
        assert "Prestige Exclusive" in result.genres

    def test_parse_genres_count(self):
        result = self._scrape_html(SAMPLE_DETAIL_HTML)
        assert len(result.genres) == 3

    # ─── Actresses ──────────────────────────────────────────

    def test_parse_actresses_count(self):
        result = self._scrape_html(SAMPLE_DETAIL_HTML)
        assert len(result.actresses) == 2

    def test_parse_actress_name(self):
        result = self._scrape_html(SAMPLE_DETAIL_HTML)
        actress = result.actresses[0]
        assert actress.last_name == "Suzuki"
        assert actress.first_name == "Koharu"

    def test_parse_actress_alias_japanese(self):
        """Japanese alias should be captured as japanese_name."""
        result = self._scrape_html(SAMPLE_DETAIL_HTML)
        assert result.actresses[0].japanese_name == "鈴木心春"

    def test_parse_actress_no_alias(self):
        """Actress without alias should still parse."""
        result = self._scrape_html(SAMPLE_DETAIL_HTML)
        actress = result.actresses[1]
        assert actress.last_name == "Yamagishi"
        assert actress.first_name == "Aika"
        assert actress.japanese_name is None

    def test_parse_japanese_actress_name(self):
        """Japanese-only name should go to japanese_name."""
        result = self._scrape_html(SAMPLE_JAPANESE_ACTRESS_HTML)
        assert len(result.actresses) == 1
        assert result.actresses[0].japanese_name == "鈴木心春"
        assert result.actresses[0].first_name is None
        assert result.actresses[0].last_name is None

    @pytest.mark.asyncio
    async def test_search_reraises_cloudflare_block(self):
        scraper = JavlibraryScraper(http=_BlockedHttpClient())

        with pytest.raises(CloudflareBlockedError):
            await scraper.search("ABP-420")

    @pytest.mark.asyncio
    async def test_scrape_reraises_cloudflare_block(self):
        scraper = JavlibraryScraper(http=_BlockedHttpClient())

        with pytest.raises(CloudflareBlockedError):
            await scraper.scrape("https://www.javlibrary.com/en/?v=javme12345")

    # ─── Cover URL ──────────────────────────────────────────

    def test_parse_cover_url(self):
        result = self._scrape_html(SAMPLE_DETAIL_HTML)
        assert result.cover_url is not None
        assert result.cover_url.startswith("https://")
        assert "pl.jpg" in result.cover_url

    def test_parse_cover_url_now_printing(self):
        """'now_printing' cover should be filtered out."""
        html = SAMPLE_DETAIL_HTML.replace("118abp00420pl.jpg", "now_printing.jpg")
        result = self._scrape_html(html)
        assert result.cover_url is None

    # ─── Screenshots ────────────────────────────────────────

    def test_parse_screenshot_urls(self):
        result = self._scrape_html(SAMPLE_DETAIL_HTML)
        assert len(result.screenshot_urls) == 2

    def test_parse_screenshots_converted(self):
        """Screenshot URLs should be converted from thumb to full-size."""
        result = self._scrape_html(SAMPLE_DETAIL_HTML)
        for url in result.screenshot_urls:
            assert "jp-" in url  # '-' replaced with 'jp-'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scraper_cls", "html", "expected_url"),
    [
        (
            JavlibraryScraper,
            SAMPLE_DIRECT_MATCH_WITH_CANONICAL,
            "https://www.javlibrary.com/en/?v=javme12345",
        ),
        (
            JavlibraryScraper,
            SAMPLE_DIRECT_MATCH_WITHOUT_CANONICAL,
            "https://www.javlibrary.com/en/vl_searchbyid.php?keyword=ABP-420",
        ),
        (
            JavlibraryJaScraper,
            SAMPLE_DIRECT_MATCH_WITH_CANONICAL,
            "https://www.javlibrary.com/ja/?v=javme12345",
        ),
        (
            JavlibraryJaScraper,
            SAMPLE_DIRECT_MATCH_WITHOUT_CANONICAL,
            "https://www.javlibrary.com/ja/vl_searchbyid.php?keyword=ABP-420",
        ),
        (
            JavlibraryZhScraper,
            SAMPLE_DIRECT_MATCH_WITH_CANONICAL,
            "https://www.javlibrary.com/cn/?v=javme12345",
        ),
        (
            JavlibraryZhScraper,
            SAMPLE_DIRECT_MATCH_WITHOUT_CANONICAL,
            "https://www.javlibrary.com/cn/vl_searchbyid.php?keyword=ABP-420",
        ),
    ],
)
async def test_search_direct_match_returns_real_or_reusable_url(
    scraper_cls,
    html: str,
    expected_url: str,
):
    """Direct-match search should never fall back to the fake _detail_ URL."""
    scraper = scraper_cls(http=_FakeHttpClient(html))

    result = await scraper.search("ABP-420")

    assert result == expected_url
    assert "_detail_" not in result

    # ─── Search Results Parsing ─────────────────────────────

    def test_parse_search_results(self):
        results = JavlibraryScraper._parse_search_results(SAMPLE_SEARCH_RESULTS_HTML)
        assert len(results) == 3

    def test_parse_search_results_ids(self):
        results = JavlibraryScraper._parse_search_results(SAMPLE_SEARCH_RESULTS_HTML)
        ids = [r["id"] for r in results]
        assert "ABP-420" in ids
        assert "SSIS-001" in ids

    def test_parse_search_results_bluray_dedup(self):
        """When filtering matches, Blu-ray versions should be deprioritized."""
        results = JavlibraryScraper._parse_search_results(SAMPLE_SEARCH_RESULTS_HTML)
        abp_matches = [r for r in results if r["id"] == "ABP-420"]
        assert len(abp_matches) == 2

        # Filter Blu-ray (as the search method does)
        non_bd = [m for m in abp_matches if "blu-ray" not in m.get("title", "").lower()]
        assert len(non_bd) == 1
        assert "Blu-ray" not in non_bd[0]["title"]

    # ─── Edge Cases ─────────────────────────────────────────

    def test_empty_detail_page(self):
        """Page with minimal data should parse without errors."""
        result = self._scrape_html(SAMPLE_EMPTY_DETAIL_HTML)
        assert result.id == "ABP-999"
        assert result.title is None or result.title == "Unknown"
        assert result.director is None
        assert result.actresses == []
        assert result.genres == []
