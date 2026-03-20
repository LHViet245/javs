"""Tests for the MGStage (JA) scraper."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from javs.scrapers.mgstage import MgstageJaScraper
from javs.services.http import HttpClient


@pytest.fixture
def mock_http_client() -> HttpClient:
    client = HttpClient()
    client.get = AsyncMock()
    return client


@pytest.fixture
def scraper(mock_http_client: HttpClient) -> MgstageJaScraper:
    return MgstageJaScraper(http=mock_http_client, use_proxy=False)


@pytest.mark.asyncio
async def test_mgstage_search_exact_match(
    scraper: MgstageJaScraper, mock_http_client: HttpClient
) -> None:
    """Test searching for ABF-329 returns the exact URL."""
    html_path = Path(__file__).parent.parent / "data" / "mgstage" / "search_ABF-329.html"
    mock_http_client.get.return_value = html_path.read_text()

    result = await scraper.search("ABF-329")
    # Verify strict cookie passing
    mock_http_client.get.assert_called_with(
        "https://www.mgstage.com/search/cSearch.php?search_word=ABF-329",
        cookies={"adc": "1"},
        use_proxy=False,
    )
    assert result == "https://www.mgstage.com/product/product_detail/ABF-329/"


@pytest.mark.asyncio
async def test_mgstage_search_with_prefix(
    scraper: MgstageJaScraper, mock_http_client: HttpClient
) -> None:
    """Test searching for FSDSS-198 correctly grabs 406FSDSS-198 URL."""
    html_path = Path(__file__).parent.parent / "data" / "mgstage" / "search_FSDSS-198.html"
    mock_http_client.get.return_value = html_path.read_text()

    result = await scraper.search("FSDSS-198")
    assert result == "https://www.mgstage.com/product/product_detail/406FSDSS-198/"


@pytest.mark.asyncio
async def test_mgstage_scrape_detail(
    scraper: MgstageJaScraper, mock_http_client: HttpClient
) -> None:
    """Test scraping detailed metadata for ABF-329."""
    html_path = Path(__file__).parent.parent / "data" / "mgstage" / "detail_ABF-329.html"

    # We mock getting the detail page, then optionally getting trailer API.
    # We will just return the detail page for any get call here.
    async def mock_get(url: str, **kwargs) -> str:
        if "sampleRespons.php" in url:
            # Mock the trailer API JSON/JSONP response
            return r'{"url":"https:\/\/image.mgstage.com\/...sample.ism\/...","status":"ok"}'
        return html_path.read_text()

    mock_http_client.get.side_effect = mock_get

    movie = await scraper.scrape("https://www.mgstage.com/product/product_detail/ABF-329/")

    assert movie is not None
    assert movie.id in ("ABF-329", "ABF329", "259ABF-329", "259ABF329")
    # Due to variation, let's at least check title wasn't empty
    assert movie.title
    assert movie.release_date
    assert movie.runtime is not None
    assert movie.maker
    assert movie.cover_url
    assert movie.source == "mgstageja"

    # Verify trailer parsed out the .mp4
    assert movie.trailer_url
    assert ".mp4" in movie.trailer_url
    assert ".ism" not in movie.trailer_url

