"""Tests for the DMM scraper."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from javs.scrapers.dmm import DmmScraper
from javs.services.http import HttpClient

SAMPLE_SEARCH_RESULT_HTML = """
<html>
<body>
  <div id="list">
    <li>
      <div class="tmb">
        <a href="https://www.dmm.co.jp/mono/dvd/-/detail/=/cid=1abp00420/">ABP-420</a>
      </div>
    </li>
  </div>
</body>
</html>
"""

SAMPLE_EMPTY_SEARCH_RESULT_HTML = """
<html><body><div id="list"><p>No result</p></div></body></html>
"""

SAMPLE_DETAIL_HTML = """
<html>
<body>
  <h1 id="title" class="item fn">Sample Movie Title</h1>
  <p class="mg-b20">Sample description</p>
  <table>
    <tr><td>発売日：</td><td>2023/06/15</td></tr>
    <tr><td>収録時間：</td><td>120分</td></tr>
    <tr>
      <td>監督：</td>
      <td><a href="/mono/dvd/-/list/=/article=director/id=123/">Test Director</a></td>
    </tr>
    <tr>
      <td>メーカー：</td>
      <td><a href="/mono/dvd/-/list/=/article=maker/id=456/">Test Maker</a></td>
    </tr>
    <tr>
      <td>レーベル：</td>
      <td><a href="/mono/dvd/-/list/=/article=label/id=789/">Test Label</a></td>
    </tr>
    <tr>
      <td>シリーズ：</td>
      <td><a href="/mono/dvd/-/list/=/article=series/id=321/">Test Series</a></td>
    </tr>
    <tr>
      <td>ジャンル：</td>
      <td>
        <a href="/genre1">Drama</a>
        <a href="/genre2">Exclusive</a>
      </td>
    </tr>
  </table>
  <div><strong>4.5 points</strong></div>
  <div class="d-review__evaluates"><strong>12</strong></div>
  <a href="/mono/dvd/-/list/=/article=actress/id=111/">Kamiki Rei</a>
  <img src="https://pics.dmm.co.jp/mono/movie/adult/1abp00420/1abp00420ps.jpg">
  <a name="sample-image">
    <img data-lazy="https://pics.dmm.co.jp/digital/video/1abp00420/1abp00420-1.jpg">
  </a>
  <a name="sample-image">
    <img src="https://pics.dmm.co.jp/digital/video/1abp00420/1abp00420-2.jpg">
  </a>
  <script>
    window.__DATA__ = (
      "&quot;video_url&quot;:&quot;"
      "https:\\/\\/cc3001.dmm.co.jp\\/litevideo\\/freepv\\/a\\/abp420.mp4&quot;"
    );
  </script>
</body>
</html>
"""

SAMPLE_ACTRESS_OG_HTML = """
<html>
<head>
  <meta property="og:image" content="https://image-optimizer.osusume.dmm.co.jp/og?imgUrl=https%3A%2F%2Fpics.dmm.co.jp%2Fmono%2Factjpgs%2Fkamiki_rei.jpg&amp;name=Kamiki">
</head>
</html>
"""

SAMPLE_ACTRESS_LEGACY_HTML = """
<html><body><img src="https://pics.dmm.co.jp/mono/actjpgs/legacy_name.jpg"></body></html>
"""

SAMPLE_SPA_HTML = """
<html><body>BAILOUT_TO_CLIENT_SIDE_RENDERING</body></html>
"""

SAMPLE_TRAILER_IFRAME_HTML = """
<html><body><iframe src="//www.dmm.co.jp/litevideo/-/part/=/cid=1abp00420/"></iframe></body></html>
"""

SAMPLE_TRAILER_PAGE_HTML = """
<html><body>
  <video src="//cc3001.dmm.co.jp/litevideo/freepv/1/1ab/1abp00420/1abp00420_dmb_w.mp4"></video>
</body></html>
"""


@pytest.fixture
def mock_http_client() -> HttpClient:
    client = HttpClient()
    client.get = AsyncMock()
    client.get_json = AsyncMock()
    return client


@pytest.fixture
def scraper(mock_http_client: HttpClient) -> DmmScraper:
    return DmmScraper(http=mock_http_client, use_proxy=True)


class TestDmmSearch:
    """Verify DMM search routing and fallback behavior."""

    @pytest.mark.asyncio
    async def test_search_returns_first_digital_match(
        self, scraper: DmmScraper, mock_http_client: HttpClient
    ) -> None:
        mock_http_client.get.return_value = SAMPLE_SEARCH_RESULT_HTML

        result = await scraper.search("ABP-420")

        assert result == "https://www.dmm.co.jp/mono/dvd/-/detail/=/cid=1abp00420/"
        mock_http_client.get.assert_awaited_once()
        args = mock_http_client.get.await_args_list[0]
        assert args.args[0] == "https://www.dmm.co.jp/digital/videoa/-/list/search/=/searchstr=abp420/"
        assert args.kwargs["use_proxy"] is True
        assert args.kwargs["cookies"]["cklg"] == "ja"
        assert args.kwargs["cookies"]["ckcy"] == "1"

    @pytest.mark.asyncio
    async def test_search_falls_back_to_physical_results_when_digital_is_empty(
        self, scraper: DmmScraper, mock_http_client: HttpClient
    ) -> None:
        mock_http_client.get.side_effect = [
            SAMPLE_EMPTY_SEARCH_RESULT_HTML,
            SAMPLE_SEARCH_RESULT_HTML,
        ]

        result = await scraper.search("ABP-420")

        assert result == "https://www.dmm.co.jp/mono/dvd/-/detail/=/cid=1abp00420/"
        assert mock_http_client.get.await_count == 2
        assert (
            mock_http_client.get.await_args_list[1].args[0]
            == "https://www.dmm.co.jp/mono/dvd/-/search/=/searchstr=abp420/"
        )


class TestDmmScrape:
    """Verify DMM scrape behavior for legacy and SPA-backed pages."""

    @pytest.mark.asyncio
    async def test_scrape_parses_detail_page_fields_and_actress_thumb(
        self, scraper: DmmScraper, mock_http_client: HttpClient
    ) -> None:
        async def fake_get(url: str, **_kwargs) -> str:
            if "actress_id=111" in url:
                return SAMPLE_ACTRESS_OG_HTML
            return SAMPLE_DETAIL_HTML

        mock_http_client.get.side_effect = fake_get

        movie = await scraper.scrape("https://www.dmm.co.jp/mono/dvd/-/detail/=/cid=1abp00420/")

        assert movie is not None
        assert movie.id == "ABP-420"
        assert movie.content_id == "1abp00420"
        assert movie.title == "Sample Movie Title"
        assert movie.description == "Sample description"
        assert movie.runtime == 120
        assert movie.director == "Test Director"
        assert movie.maker == "Test Maker"
        assert movie.label == "Test Label"
        assert movie.series == "Test Series"
        assert movie.rating is not None
        assert movie.rating.rating == 9.0
        assert movie.rating.votes == 12
        assert movie.genres == ["Drama", "Exclusive"]
        assert movie.cover_url == "https://pics.dmm.co.jp/mono/movie/adult/1abp00420/1abp00420pl.jpg"
        assert movie.screenshot_urls == [
            "https://pics.dmm.co.jp/digital/video/1abp00420/1abp00420jp-1.jpg",
            "https://pics.dmm.co.jp/digital/video/1abp00420/1abp00420jp-2.jpg",
        ]
        assert len(movie.actresses) == 1
        assert movie.actresses[0].last_name == "Kamiki"
        assert movie.actresses[0].first_name == "Rei"
        assert movie.actresses[0].thumb_url == "https://pics.dmm.co.jp/mono/actjpgs/kamiki_rei.jpg"

    @pytest.mark.asyncio
    async def test_scrape_resolves_spa_page_to_legacy_detail(
        self, scraper: DmmScraper, mock_http_client: HttpClient
    ) -> None:
        async def fake_get(url: str, **_kwargs) -> str:
            if "digital/videoa" in url:
                return SAMPLE_SPA_HTML
            return """
            <html><body>
              <h1 id="title" class="item fn">Resolved Movie</h1>
              <p class="mg-b20">Resolved</p>
            </body></html>
            """

        mock_http_client.get.side_effect = fake_get
        mock_http_client.get_json.return_value = {
            "result": [
                {
                    "detail_url": "https://www.dmm.co.jp/mono/dvd/-/detail/=/cid=1abp00420/",
                }
            ]
        }

        movie = await scraper.scrape(
            "https://www.dmm.co.jp/digital/videoa/-/detail/=/cid=1abp00420/"
        )

        assert movie is not None
        assert movie.id == "ABP-420"
        assert movie.content_id == "1abp00420"
        assert movie.title == "Resolved Movie"
        mock_http_client.get_json.assert_awaited_once_with(
            "https://www.dmm.co.jp/mono/-/detail/get-product-for-another-ajax/?content_id=1abp00420",
            cookies={"age_check_done": "1", "ckcy": "1", "cklg": "ja"},
            use_proxy=True,
        )


class TestDmmHelpers:
    """Verify focused parser helper behavior."""

    @pytest.mark.asyncio
    async def test_fetch_actress_thumb_falls_back_to_legacy_image(
        self, mock_http_client: HttpClient
    ):
        scraper = DmmScraper(http=mock_http_client, use_proxy=False)
        mock_http_client.get.return_value = SAMPLE_ACTRESS_LEGACY_HTML

        thumb = await scraper._fetch_actress_thumb("111")

        assert thumb == "https://pics.dmm.co.jp/mono/actjpgs/legacy_name.jpg"

    @pytest.mark.asyncio
    async def test_parse_trailer_url_supports_legacy_iframe_flow(
        self, mock_http_client: HttpClient
    ) -> None:
        scraper = DmmScraper(http=mock_http_client, use_proxy=False)

        async def fake_get(url: str, **_kwargs) -> str:
            if "sample/player.html" in url:
                return SAMPLE_TRAILER_IFRAME_HTML
            return SAMPLE_TRAILER_PAGE_HTML

        mock_http_client.get.side_effect = fake_get

        trailer = await scraper._parse_trailer_url(
            "<a onclick=\"sampleplay('/sample/player.html')\">Play</a>"
        )

        assert (
            trailer
            == "https://cc3001.dmm.co.jp/litevideo/freepv/1/1ab/1abp00420/1abp00420_dmb_w.mp4"
        )

    @pytest.mark.asyncio
    async def test_parse_trailer_url_supports_new_embedded_format(
        self, mock_http_client: HttpClient
    ) -> None:
        scraper = DmmScraper(http=mock_http_client, use_proxy=False)

        trailer = await scraper._parse_trailer_url(
            '&quot;video_url&quot;:&quot;https:\\/\\/cc3001.dmm.co.jp\\/litevideo\\/freepv\\/'
            'a\\/abp420.mp4&quot;'
        )

        assert trailer == "https://cc3001.dmm.co.jp/litevideo/freepv/a/abp420.mp4"

    def test_parse_id_supports_suffixes_and_missing_content_id(self, mock_http_client: HttpClient):
        scraper = DmmScraper(http=mock_http_client, use_proxy=False)

        assert scraper._parse_id("https://www.dmm.co.jp/mono/dvd/-/detail/=/cid=12abw00045so/") == (
            "ABW-045SO"
        )
        assert scraper._parse_id("https://www.dmm.co.jp/detail/no-cid") is None
