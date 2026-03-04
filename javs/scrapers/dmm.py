"""DMM scraper for Japanese and English metadata.

Replaces Javinizer's Scraper.Dmm.ps1 (472 lines) + Private/Get-DmmUrl.ps1.
"""

from __future__ import annotations

import re
from datetime import date
from typing import ClassVar

from javs.models.movie import Actress, MovieData, Rating
from javs.scrapers.base import BaseScraper
from javs.scrapers.registry import ScraperRegistry
from javs.services.http import DMM_COOKIES
from javs.utils.html import extract_attr, extract_text, parse_html


@ScraperRegistry.register
class DmmScraper(BaseScraper):
    """Scraper for DMM.co.jp (English site)."""

    name: ClassVar[str] = "dmm"
    display_name: ClassVar[str] = "DMM (Japanese)"
    languages: ClassVar[list[str]] = ["ja"]
    base_url: ClassVar[str] = "https://www.dmm.co.jp"

    SEARCH_URL = "https://www.dmm.co.jp/mono/dvd/-/search/=/searchstr={id}/"
    DIGITAL_SEARCH_URL = "https://www.dmm.co.jp/digital/videoa/-/list/search/=/searchstr={id}/"

    async def search(self, movie_id: str) -> str | None:
        """Search DMM for a movie by ID."""
        normalized = self.normalize_id(movie_id)
        content_id = self._id_to_content_id(normalized)

        ja_cookies = {**DMM_COOKIES, "cklg": "ja", "ckcy": "1"}

        # Try digital first, then physical
        for url_template in [self.DIGITAL_SEARCH_URL, self.SEARCH_URL]:
            search_url = url_template.format(id=content_id)
            try:
                html = await self.http.get(search_url, cookies=ja_cookies, use_proxy=self.use_proxy)
                soup = parse_html(html)

                # Find the first result link
                link = soup.select_one("#list li .tmb a")
                if link:
                    href = extract_attr(link, "href")
                    if href:
                        return href
            except Exception as exc:
                self.logger.debug("dmm_search_error", url=search_url, error=str(exc))

        return None

    async def scrape(self, url: str) -> MovieData | None:
        """Scrape movie metadata from DMM detail page."""
        ja_cookies = {**DMM_COOKIES, "cklg": "ja", "ckcy": "1"}
        
        # Address new SPA URLs by intercepting and redirecting to the legacy physical page
        if "video.dmm.co.jp/av/content" in url:
            match = re.search(r"id=([a-zA-Z0-9]+)", url)
            if match:
                content_id = match.group(1)
                fallback_url = f"https://www.dmm.co.jp/mono/-/detail/get-product-for-another-ajax/?content_id={content_id}"
                self.logger.debug("dmm_spa_redirect", content_id=content_id, fallback_url=fallback_url)
                try:
                    data = await self.http.get_json(fallback_url, cookies=ja_cookies, use_proxy=self.use_proxy)
                    result_list = data.get("result", [])
                    if result_list and isinstance(result_list, list):
                        legacy_url = result_list[0].get("detail_url")
                        if legacy_url:
                            self.logger.debug("dmm_spa_resolved", original_url=url, target_url=legacy_url)
                            url = legacy_url
                except Exception as exc:
                    self.logger.warning("dmm_spa_redirect_failed", error=str(exc), url=url)

        try:
            html = await self.http.get(url, cookies=ja_cookies, use_proxy=self.use_proxy)
        except Exception as exc:
            self.logger.error("dmm_scrape_error", url=url, error=str(exc))
            return None

        soup = parse_html(html)

        # Extract all fields
        movie_id = self._parse_id(url)
        content_id = self._parse_content_id(url)

        return MovieData(
            id=movie_id or "",
            content_id=content_id,
            title=self._parse_title(soup),
            description=self._parse_description(soup, html),
            release_date=self._parse_release_date(html),
            runtime=self._parse_runtime(html),
            director=self._parse_director(html),
            maker=self._parse_maker(html),
            label=self._parse_label(html),
            series=self._parse_series(html),
            rating=self._parse_rating(soup, html),
            actresses=self._parse_actresses(soup, html),
            genres=self._parse_genres(soup, html),
            cover_url=self._parse_cover_url(html),
            screenshot_urls=self._parse_screenshot_urls(soup),
            trailer_url=self._parse_trailer_url(html),
            source=self.name,
        )

    # ─── ID Parsing ──────────────────────────────────────────

    def _parse_content_id(self, url: str) -> str | None:
        """Extract content ID from DMM URL (cid=xxx)."""
        match = re.search(r"cid=([^/&]+)", url)
        return match.group(1) if match else None

    def _parse_id(self, url: str) -> str | None:
        """Convert DMM content ID to standard JAV ID format."""
        content_id = self._parse_content_id(url)
        if not content_id:
            return None

        match = re.search(r"\d*([a-z]+)(\d+)(.*)$", content_id, re.IGNORECASE)
        if not match or not match.group(1) or not match.group(2):
            return None

        prefix = match.group(1).upper()
        number = match.group(2).lstrip("0").zfill(3)
        suffix = match.group(3).upper() if match.group(3) else ""
        return f"{prefix}-{number}{suffix}"

    @staticmethod
    def _id_to_content_id(movie_id: str) -> str:
        """Convert JAV ID to DMM search-compatible format."""
        return movie_id.replace("-", "").lower()

    # ─── Field Parsers ───────────────────────────────────────

    def _parse_title(self, soup) -> str | None:
        title_el = soup.select_one("h1#title.item.fn")
        return extract_text(title_el) or None

    def _parse_description(self, soup, html: str) -> str | None:
        # Try structured element first
        el = soup.select_one("p.mg-b20")
        if el:
            text = extract_text(el)
            if text:
                return text

        # Fallback: parse from block
        match = re.search(r'<div class="mg-b20 lh4">(.*?)</div>', html, re.DOTALL)
        if match:
            text = re.sub(r"<[^>]+>", "", match.group(1)).strip()
            return text if text else None
        return None

    def _parse_release_date(self, html: str) -> date | None:
        match = re.search(r"(\d{4})/(\d{2})/(\d{2})", html)
        if match:
            try:
                return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            except ValueError:
                return None
        return None

    def _parse_runtime(self, html: str) -> int | None:
        match = re.search(r"(\d{2,3})\s?(?:minutes|分)", html)
        return int(match.group(1)) if match else None

    def _parse_director(self, html: str) -> str | None:
        match = re.search(r'href="[^"]*\?director=\d+"[^>]*>([^<]+)</a>', html)
        return match.group(1).strip() if match else None

    def _parse_maker(self, html: str) -> str | None:
        match = re.search(
            r'<a[^>]*href="[^"]*(?:\?maker=|/article=maker/id=)\d+[^"]*"[^>]*>([\s\S]*?)</a>',
            html,
        )
        return match.group(1).strip() if match else None

    def _parse_label(self, html: str) -> str | None:
        match = re.search(
            r'<a[^>]*href="[^"]*(?:\?label=|/article=label/id=)\d+[^"]*"[^>]*>([\s\S]*?)</a>',
            html,
        )
        return match.group(1).strip() if match else None

    def _parse_series(self, html: str) -> str | None:
        match = re.search(
            r'<a href="(?:/digital/videoa/|(?:/en)?/mono/dvd/)-/list/=/article=series/id=\d*/?"[^>]*?>(.*?)</a></td>',
            html,
        )
        return match.group(1).strip() if match else None

    def _parse_rating(self, soup, html: str) -> Rating | None:
        match = re.search(r"<strong>([\d.]+)\s?(?:points|点)</strong>", html)
        if not match:
            return None

        rating_str = match.group(1)
        try:
            rating_val = float(rating_str) * 2  # Convert 1-5 to 1-10 scale
        except ValueError:
            return None

        if rating_val == 0:
            return None

        # Get vote count
        votes = 0
        vote_match = re.search(r"d-review__evaluates.*?<strong>(\d+)</strong>", html, re.DOTALL)
        if vote_match:
            votes = int(vote_match.group(1))

        return Rating(rating=round(rating_val, 2), votes=votes)

    def _parse_actresses(self, soup, html: str) -> list[Actress]:
        """Parse actresses from DMM detail page."""
        actresses = []

        # Find actress links (supports both digital and mono patterns)
        matches = re.findall(
            r'<a.*?href="[^"]*(?:\?actress=|article=actress/id=)(\d+)[/"].*?>([^<]+)</a>',
            html,
        )

        for actress_id, actress_name in matches:
            name = actress_name.strip()
            first_name = None
            last_name = None
            japanese_name = None

            # Check if name is Japanese
            if re.search(r"[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]", name):
                japanese_name = re.sub(r"（.*）", "", name).strip()
            else:
                # English name
                parts = name.split()
                if len(parts) >= 2:
                    last_name = parts[0].title()
                    first_name = parts[1].title()
                else:
                    first_name = name.title()

            actresses.append(
                Actress(
                    last_name=last_name,
                    first_name=first_name,
                    japanese_name=japanese_name,
                )
            )

        return actresses

    def _parse_genres(self, soup, html: str) -> list[str]:
        """Parse genre list from DMM page."""
        genres = []

        # Find genre section
        genre_match = re.search(r">(Genre:|ジャンル：)</td>\s*\n(.*)", html, re.DOTALL)
        if not genre_match:
            return genres

        # Extract genre block
        block_match = re.split(r">(Genre:|ジャンル：)", html)
        if len(block_match) < 3:
            return genres

        genre_block = block_match[2].split("</tr>")[0]
        genre_links = re.findall(r">([^<]+)<", genre_block)

        import html as pyhtml

        for g in genre_links:
            g = pyhtml.unescape(re.sub(r"<[^>]+>", "", g)).strip()
            if g and g not in ("/a", "---"):
                genres.append(g)

        return genres

    def _parse_cover_url(self, html: str) -> str | None:
        match = re.search(
            r"(https://pics\.dmm\.co\.jp/(mono/movie/adult|digital/(?:video|amateur))/.*/.*\.jpg)",
            html,
        )
        if match:
            # Replace small image suffix with large
            return match.group(1).replace("ps.jpg", "pl.jpg")
        return None

    def _parse_screenshot_urls(self, soup) -> list[str]:
        screenshots = []
        for link in soup.select('a[name="sample-image"] img'):
            src = extract_attr(link, "data-lazy") or extract_attr(link, "src")
            if src:
                # Convert to full-size
                screenshots.append(src.replace("-", "jp-"))
        return screenshots

    def _parse_trailer_url(self, html: str) -> str | None:
        # Legacy/Standard format: onclick="sampleplay('https://cc3001...')"
        match = re.search(r"onclick.+(?:vr)?sampleplay\('([^']+)'\)", html)
        if match:
            return match.group(1)
            
        # New format (2025+): onclick="gaEventVideoStart('{&quot;video_url&quot;:&quot;https:\/\/cc3001.dmm.co.jp...&quot;}')"
        # We look for https:\/\/[^&]+.mp4
        match_new = re.search(r"&quot;video_url&quot;:&quot;(https:\\/\\/[^&]+\.mp4)&quot;", html)
        if match_new:
            # We must unescape the JSON slashes
            url = match_new.group(1).replace(r"\/", "/")
            return url
            
        return None

