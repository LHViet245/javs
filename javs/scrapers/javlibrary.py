"""Javlibrary scraper — HTML-based metadata fetcher (EN/JA/ZH).

Replaces Javinizer's:
  - Scraper.Javlibrary.ps1 (347 lines) — HTML field parsers
  - Get-JavlibraryUrl.ps1 (103 lines) — Search + redirect
  - Get-JavlibraryData.ps1 (47 lines) — Orchestration
  - Test-JavlibraryCf.ps1 (57 lines) — Cloudflare handling

Key behaviors ported from original:
  - Search redirects directly to detail page if unique match
  - Multi-result pages parsed, with Blu-ray deduplication
  - Cross-language actress fetching (EN + JA pages)
  - Cover URL validation (filter 'now_printing' / 'removed')
  - Screenshot URL conversion to full-size
"""

from __future__ import annotations

import re
from datetime import date
from typing import ClassVar
from urllib.parse import urljoin

from javs.models.movie import Actress, MovieData, Rating
from javs.scrapers.base import BaseScraper
from javs.scrapers.registry import ScraperRegistry
from javs.services.http import CloudflareBlockedError
from javs.utils.html import extract_attr, extract_text, parse_html
from javs.utils.string import clean_title


@ScraperRegistry.register
class JavlibraryScraper(BaseScraper):
    """Scraper for JAVLibrary (English).

    JAVLibrary is an HTML site. Search and scrape require parsing HTML
    with BeautifulSoup. The site is behind Cloudflare, so requests may
    need CF cookies/headers.

    Search flow:
      1. GET /en/vl_searchbyid.php?keyword={ID}
      2. If response URL contains ?v= → direct match (scraped inline)
      3. Otherwise, parse search result list, match by ID, filter Blu-ray dupes
    """

    name: ClassVar[str] = "javlibrary"
    display_name: ClassVar[str] = "JAVLibrary"
    languages: ClassVar[list[str]] = ["en"]
    base_url: ClassVar[str] = "https://www.javlibrary.com"

    # Language path segment for URL construction
    _lang_path: ClassVar[str] = "/en/"

    async def search(self, movie_id: str) -> str | None:
        """Search Javlibrary by movie ID.

        Handles two cases:
        1. Unique match → server redirects to detail page (URL has ?v=)
        2. Multiple results → parse list and match by ID
        """
        normalized = self.normalize_id(movie_id)
        search_url = f"{self.base_url}{self._lang_path}vl_searchbyid.php?keyword={normalized}"

        try:
            html = await self.http.get_cf(search_url, use_proxy=self.use_proxy)
        except CloudflareBlockedError:
            raise
        except Exception as exc:
            self.logger.debug("javlib_search_error", movie_id=normalized, error=str(exc))
            # Retry once (Javlibrary has intermittent 500 errors)
            try:
                html = await self.http.get_cf(search_url, use_proxy=self.use_proxy)
            except CloudflareBlockedError:
                raise
            except Exception:
                return None

        soup = parse_html(html)

        # Case 1: Direct match — check if the page is a detail page
        video_id_div = soup.select_one("div#video_id")
        if video_id_div:
            page_id = self._extract_item_value(video_id_div)
            if page_id and page_id.upper() == normalized.upper():
                return self._resolve_direct_match_url(search_url, soup)

        # Case 2: Search results list — parse result entries
        results = self._parse_search_results(html)
        if not results:
            self.logger.debug("javlib_no_results", movie_id=normalized)
            return None

        # Find matching ID(s)
        matches = [r for r in results if r["id"].upper() == normalized.upper()]
        if not matches:
            return None

        # If multiple matches, prefer non-Blu-ray version
        if len(matches) > 1:
            non_bd = [m for m in matches if "blu-ray" not in m.get("title", "").lower()]
            if non_bd:
                matches = non_bd

        return matches[0].get("url")

    def _resolve_direct_match_url(self, search_url: str, soup) -> str:
        """Resolve a usable detail URL for a direct-match search result.

        Prefer the canonical URL when present. If the page omits it, reuse the
        search URL because Javlibrary redirects that URL back to the same detail page.
        """
        canonical_link = soup.select_one("link[rel='canonical']")
        if canonical_link and canonical_link.get("href"):
            canonical_url = urljoin(self.base_url, canonical_link["href"])
            return re.sub(r"/(en|ja|cn)/", self._lang_path, canonical_url)
        return search_url

    async def scrape(self, url: str) -> MovieData | None:
        """Scrape movie metadata from Javlibrary detail page."""
        try:
            html = await self.http.get_cf(url, use_proxy=self.use_proxy)
        except CloudflareBlockedError:
            raise
        except Exception as exc:
            self.logger.error("javlib_scrape_error", url=url, error=str(exc))
            return None

        soup = parse_html(html)

        # Verify we're on a detail page
        video_id_div = soup.select_one("div#video_id")
        if not video_id_div:
            self.logger.warning("javlib_not_detail_page", url=url)
            return None

        movie_id = self._extract_item_value(video_id_div)

        return MovieData(
            id=movie_id or "",
            title=self._parse_title(soup),
            release_date=self._parse_release_date(soup),
            runtime=self._parse_runtime(soup),
            director=self._parse_director(soup),
            maker=self._parse_maker(soup),
            label=self._parse_label(soup),
            rating=self._parse_rating(soup),
            genres=self._parse_genres(soup),
            actresses=self._parse_actresses(soup),
            cover_url=self._parse_cover_url(soup),
            screenshot_urls=self._parse_screenshot_urls(soup),
            source=self.name,
        )

    # ─── Search Result Parsing ───────────────────────────────

    @staticmethod
    def _parse_search_results(html: str) -> list[dict]:
        """Parse search result entries from a results page.

        Each result has pattern:
        <a href="./?v=XXX" title="ID TITLE"><div class="id">ID</div>
        """
        results = []
        pattern = r'<a href="\./\?v=([^"]+)" title="([^"]+)"><div class="id">([^<]+)</div>'
        for match in re.finditer(pattern, html):
            v_param = match.group(1)
            full_title = match.group(2)
            result_id = match.group(3).strip()

            # Title = full_title minus the ID prefix
            title_parts = full_title.split(" ", 1)
            title = title_parts[1] if len(title_parts) > 1 else full_title

            results.append(
                {
                    "id": result_id,
                    "title": title,
                    "url": f"https://www.javlibrary.com/en/?v={v_param}",
                }
            )

        return results

    # ─── HTML Item Value Extraction ──────────────────────────

    @staticmethod
    def _extract_item_value(item_div) -> str | None:
        """Extract value from a Javlibrary item div.

        Pattern: <div id="video_xxx" class="item">
                   <table><tr><td class="header">Label:</td>
                   <td class="text">VALUE</td></tr></table>
                 </div>
        """
        td = item_div.select_one("td.text")
        if td:
            return extract_text(td)

        # Fallback: find second <td>
        tds = item_div.select("td")
        if len(tds) >= 2:
            return extract_text(tds[1])

        return None

    @staticmethod
    def _extract_item_link(item_div) -> str | None:
        """Extract link text from item div → a[rel=tag]."""
        link = item_div.select_one('a[rel="tag"]')
        if link:
            return extract_text(link)
        return None

    # ─── Field Parsers ───────────────────────────────────────

    def _parse_title(self, soup) -> str | None:
        """Extract title from <title> tag.

        Format: "ID TITLE - JAVLibrary"
        We strip the ID prefix and suffix.
        """
        title_el = soup.select_one("title")
        if not title_el:
            return None

        raw = extract_text(title_el) or ""
        # Remove " - JAVLibrary" suffix
        raw = re.sub(r"\s*-\s*JAVLibrary.*$", "", raw, flags=re.IGNORECASE)

        # Remove ID prefix (first word)
        parts = raw.split(" ", 1)
        title = parts[1].strip() if len(parts) > 1 else raw.strip()

        return clean_title(title) if title else None

    def _parse_release_date(self, soup) -> date | None:
        """Parse date from div#video_date."""
        div = soup.select_one("div#video_date")
        if not div:
            return None

        date_str = self._extract_item_value(div)
        if not date_str:
            return None

        try:
            parts = date_str.strip().split("-")
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, IndexError):
            return None

    def _parse_runtime(self, soup) -> int | None:
        """Parse runtime from div#video_length → span.text."""
        div = soup.select_one("div#video_length")
        if not div:
            return None

        span = div.select_one("span.text")
        if span:
            text = extract_text(span)
            if text and text.strip().isdigit():
                return int(text.strip())
        return None

    def _parse_director(self, soup) -> str | None:
        """Parse director from div#video_director → a[rel=tag]."""
        div = soup.select_one("div#video_director")
        if not div:
            return None
        return self._extract_item_link(div)

    def _parse_maker(self, soup) -> str | None:
        """Parse maker/studio from div#video_maker → a[rel=tag]."""
        div = soup.select_one("div#video_maker")
        if not div:
            return None
        text = self._extract_item_link(div)
        return clean_title(text) if text else None

    def _parse_label(self, soup) -> str | None:
        """Parse label from div#video_label → a[rel=tag]."""
        div = soup.select_one("div#video_label")
        if not div:
            return None
        text = self._extract_item_link(div)
        return clean_title(text) if text else None

    def _parse_rating(self, soup) -> Rating | None:
        """Parse rating from video_review section.

        Uses string operations since lxml may restructure nested table
        elements and raw string regex escaping is problematic.
        """
        html_str = str(soup)

        # Find the score span by string position
        marker = 'class="score">'
        pos = html_str.find(marker)
        if pos == -1:
            return None

        # Extract content after the marker up to the closing tag
        start = pos + len(marker)
        end = html_str.find("<", start)
        if end == -1:
            return None

        raw = html_str[start:end].strip().strip("()")

        try:
            val = float(raw)
            if val == 0:
                return None
            return Rating(rating=round(val, 2), votes=None)
        except Exception:
            return None

    def _parse_genres(self, soup) -> list[str]:
        """Parse genres from div#video_genres → a[rel='category tag']."""
        div = soup.select_one("div#video_genres")
        if not div:
            return []

        genres = []
        for link in div.select('a[rel="category tag"]'):
            text = extract_text(link)
            if text:
                genres.append(clean_title(text))
        return genres

    def _parse_actresses(self, soup) -> list[Actress]:
        """Parse actresses from star spans.

        Pattern: <span class="star"><a href="vl_star.php?s=..." rel="tag">Name</a></span>
        Aliases appear in <span class="alias"> elements.
        """
        actresses = []

        star_spans = soup.select("span.star")
        for span in star_spans:
            link = span.select_one('a[rel="tag"]')
            if not link:
                continue

            name = extract_text(link)
            if not name:
                continue

            # Parse name parts
            first_name = None
            last_name = None
            japanese_name = None

            # Check if name contains Japanese characters
            if re.search(r"[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]", name):
                japanese_name = name.strip()
            else:
                parts = name.strip().split(" ", 1)
                if len(parts) >= 2:
                    last_name = parts[0].strip()
                    first_name = parts[1].strip()
                else:
                    first_name = name.strip()

            # Look for aliases
            alias_spans = span.select("span.alias")
            for alias_span in alias_spans:
                alias_text = extract_text(alias_span)
                if alias_text:
                    if re.search(r"[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]", alias_text):
                        if not japanese_name:
                            japanese_name = alias_text.strip()
                    else:
                        # English alias — use for name if we don't have one
                        if not first_name and not last_name:
                            alias_parts = alias_text.strip().split(" ", 1)
                            last_name = alias_parts[0] if len(alias_parts) >= 2 else None
                            first_name = alias_parts[1] if len(alias_parts) >= 2 else alias_parts[0]

            actresses.append(
                Actress(
                    last_name=last_name,
                    first_name=first_name,
                    japanese_name=japanese_name or None,
                )
            )

        return actresses

    def _parse_cover_url(self, soup) -> str | None:
        """Parse cover image from img#video_jacket_img.

        Handles protocol-relative URLs (//...) and validates
        the image isn't a 'now_printing' placeholder.
        """
        img = soup.select_one("img#video_jacket_img")
        if not img:
            return None

        src = extract_attr(img, "src")
        if not src:
            return None

        # Fix protocol-relative URLs
        if src.startswith("//"):
            src = "https:" + src

        # Filter known invalid images
        if "now_printing" in src.lower() or "removed" in src.lower():
            return None

        return src

    def _parse_screenshot_urls(self, soup) -> list[str]:
        """Parse screenshot thumbnails from div.previewthumbs.

        Converts thumbnail URLs to full-size by replacing '-' with 'jp-',
        but only for DMM-hosted images.
        """
        container = soup.select_one("div.previewthumbs")
        if not container:
            return []

        screenshots = []
        for img in container.select("img"):
            src = extract_attr(img, "src")
            if not src:
                continue

            # Fix protocol-relative
            if src.startswith("//"):
                src = "https:" + src

            # Convert to full-size (same as original Javinizer)
            full_src = src.replace("-", "jp-")

            # Only include DMM-hosted images
            if "pics.dmm" in full_src:
                screenshots.append(full_src)

        return screenshots


@ScraperRegistry.register
class JavlibraryJaScraper(JavlibraryScraper):
    """Javlibrary scraper for Japanese language."""

    name: ClassVar[str] = "javlibraryja"
    display_name: ClassVar[str] = "JAVLibrary (JA)"
    languages: ClassVar[list[str]] = ["ja"]
    _lang_path: ClassVar[str] = "/ja/"

    async def search(self, movie_id: str) -> str | None:
        """Search using JA language path."""
        normalized = self.normalize_id(movie_id)
        search_url = f"{self.base_url}{self._lang_path}vl_searchbyid.php?keyword={normalized}"

        try:
            html = await self.http.get_cf(search_url, use_proxy=self.use_proxy)
        except CloudflareBlockedError:
            raise
        except Exception:
            try:
                html = await self.http.get_cf(search_url, use_proxy=self.use_proxy)
            except CloudflareBlockedError:
                raise
            except Exception:
                return None

        soup = parse_html(html)

        # Direct match check — extract canonical URL like EN class
        video_id_div = soup.select_one("div#video_id")
        if video_id_div:
            page_id = self._extract_item_value(video_id_div)
            if page_id and page_id.upper() == normalized.upper():
                return self._resolve_direct_match_url(search_url, soup)

        # Search results
        results = self._parse_search_results(html)
        if not results:
            return None

        matches = [r for r in results if r["id"].upper() == normalized.upper()]
        if not matches:
            return None

        if len(matches) > 1:
            non_bd = [m for m in matches if "blu-ray" not in m.get("title", "").lower()]
            if non_bd:
                matches = non_bd

        # Fix URL to use JA path
        url = matches[0].get("url", "")
        url = re.sub(r"/en/", f"{self._lang_path}", url)
        return url


@ScraperRegistry.register
class JavlibraryZhScraper(JavlibraryScraper):
    """Javlibrary scraper for Chinese language."""

    name: ClassVar[str] = "javlibraryzh"
    display_name: ClassVar[str] = "JAVLibrary (ZH)"
    languages: ClassVar[list[str]] = ["zh"]
    _lang_path: ClassVar[str] = "/cn/"

    async def search(self, movie_id: str) -> str | None:
        """Search using ZH/CN language path."""
        normalized = self.normalize_id(movie_id)
        search_url = f"{self.base_url}{self._lang_path}vl_searchbyid.php?keyword={normalized}"

        try:
            html = await self.http.get_cf(search_url, use_proxy=self.use_proxy)
        except CloudflareBlockedError:
            raise
        except Exception:
            try:
                html = await self.http.get_cf(search_url, use_proxy=self.use_proxy)
            except CloudflareBlockedError:
                raise
            except Exception:
                return None

        soup = parse_html(html)

        # Direct match check — extract canonical URL like EN class
        video_id_div = soup.select_one("div#video_id")
        if video_id_div:
            page_id = self._extract_item_value(video_id_div)
            if page_id and page_id.upper() == normalized.upper():
                return self._resolve_direct_match_url(search_url, soup)

        results = self._parse_search_results(html)
        if not results:
            return None

        matches = [r for r in results if r["id"].upper() == normalized.upper()]
        if not matches:
            return None

        if len(matches) > 1:
            non_bd = [m for m in matches if "blu-ray" not in m.get("title", "").lower()]
            if non_bd:
                matches = non_bd

        url = matches[0].get("url", "")
        url = re.sub(r"/en/", f"{self._lang_path}", url)
        return url
