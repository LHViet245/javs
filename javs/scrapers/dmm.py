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
        
        try:
            html = await self.http.get(url, cookies=ja_cookies, use_proxy=self.use_proxy)
            
            # If the response is actually the React SPA (even if hit on a legacy URL like digital/videoa)
            # DMM silently serves the SPA container instead of the legacy HTML page.
            if "video.dmm.co.jp/av/" in url or "BAILOUT_TO_CLIENT_SIDE_RENDERING" in html:
                self.logger.debug("dmm_spa_detected_in_response", url=url)
                
                # Try to extract content_id from the original url
                content_id = self._parse_content_id(url)
                if not content_id:
                     match = re.search(r"id=([a-zA-Z0-9]+)", url)
                     content_id = match.group(1) if match else None
                
                if content_id:
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
                                # Fetch the actual legacy HTML
                                html = await self.http.get(url, cookies=ja_cookies, use_proxy=self.use_proxy)
                    except Exception as exc:
                        self.logger.warning("dmm_spa_redirect_failed", error=str(exc), url=url)

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
            actresses=await self._parse_actresses(soup, html),
            genres=self._parse_genres(soup, html),
            cover_url=self._parse_cover_url(html),
            screenshot_urls=self._parse_screenshot_urls(soup),
            trailer_url=await self._parse_trailer_url(html),
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

    async def _fetch_actress_thumb(self, actress_id: str) -> str | None:
        """Fetch the actress profile page and extract the thumbnail URL.

        The actress.dmm.co.jp page is now a Next.js SPA. The actress
        thumbnail is embedded in the og:image meta tag with a URL like:
        https://image-optimizer.osusume.dmm.co.jp/actress/{name}.jpg
        We extract the imgUrl parameter from the og:image content, or
        fall back to the legacy actjpgs pattern.
        """
        url = f"https://actress.dmm.co.jp/-/detail/=/actress_id={actress_id}/"
        cookies = {**DMM_COOKIES, "ckcy": "2", "cklg": "ja", "age_check_done": "1"}
        try:
            html = await self.http.get(url, cookies=cookies, use_proxy=self.use_proxy)

            # Strategy 1: Extract from og:image meta tag (new SPA format)
            # og:image content contains a URL like:
            #   https://image-optimizer.osusume.dmm.co.jp/og?imgUrl=<encoded_url>&name=...
            # The imgUrl param points to the actual actress image.
            og_match = re.search(
                r'og:image"?\s+content="([^"]+)"', html
            )
            if og_match:
                from urllib.parse import unquote, urlparse, parse_qs

                og_url = og_match.group(1).replace("&amp;", "&")
                parsed = urlparse(og_url)
                params = parse_qs(parsed.query)
                if "imgUrl" in params:
                    thumb = unquote(params["imgUrl"][0])
                    self.logger.debug(
                        "dmm_actress_thumb_from_og",
                        actress_id=actress_id,
                        thumb_url=thumb,
                    )
                    return thumb

            # Strategy 2: Legacy actjpgs pattern (fallback)
            legacy_match = re.search(
                r'<img[^>]*src="([^"]*actjpgs[^"]+)"', html
            )
            if legacy_match:
                return legacy_match.group(1)

        except Exception as exc:
            self.logger.debug(
                "dmm_fetch_actress_thumb_failed",
                actress_id=actress_id,
                error=str(exc),
            )
        return None

    async def _parse_actresses(self, soup, html: str) -> list[Actress]:
        """Parse actresses from DMM detail page."""
        actresses = []

        # Find actress links (supports both digital and mono patterns)
        matches = re.findall(
            r'<a.*?href="[^"]*(?:\?actress=|article=actress/id=)(\d+)[/"].*?>([^<]+)</a>',
            html,
        )

        # First pass to parse names
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

            # Deduplicate by ID
            if not any(a[0] == actress_id for a in actresses):
                actresses.append(
                    (actress_id, Actress(
                        last_name=last_name,
                        first_name=first_name,
                        japanese_name=japanese_name,
                    ))
                )

        import asyncio
        for i in range(0, len(actresses), 5):
            batch = actresses[i:i+5]
            tasks = [self._fetch_actress_thumb(actress_id) for actress_id, _ in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for (_, actress_model), thumb_url in zip(batch, results, strict=False):
                if isinstance(thumb_url, str):
                    actress_model.thumb_url = thumb_url

        return [a[1] for a in actresses]

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

    async def _parse_trailer_url(self, html: str) -> str | None:
        # Legacy/Standard format: onclick="sampleplay('https://cc3001...')"
        match = re.search(r"onclick.+(?:vr)?sampleplay\('([^']+)'\)", html)
        if match:
            iframe_path = match.group(1)
            iframe_url = f"https://www.dmm.co.jp{iframe_path}"
            
            # Need specific cookies for embedded players
            cookies = {**DMM_COOKIES, "ckcy": "2", "cklg": "en", "age_check_done": "1"}
            try:
                iframe_html = await self.http.get(iframe_url, cookies=cookies, use_proxy=self.use_proxy)
                
                # Check for VR sample player directly inside this iframe
                if "vr-sample-player" in iframe_url:
                    vr_match = re.search(r"//cc3001\.dmm\.co\.jp/vrsample[^\"]+", iframe_html)
                    if vr_match:
                        url = vr_match.group(0)
                        return f"https:{url}" if url.startswith("//") else url
                        
                # Standard legacy iframe has another iframe inside it
                src_match = re.search(r'src="([^"]+)"', iframe_html)
                if src_match:
                    trailer_page_url = src_match.group(1).replace("/en", "")
                    # Ensure absolute url
                    if trailer_page_url.startswith("//"):
                        trailer_page_url = f"https:{trailer_page_url}"
                    elif trailer_page_url.startswith("/"):
                        trailer_page_url = f"https://www.dmm.co.jp{trailer_page_url}"
                        
                    trailer_html = await self.http.get(trailer_page_url, cookies=cookies, use_proxy=self.use_proxy)
                    mp4_match = re.search(r"//cc3001\.dmm\.co\.jp/litevideo/freepv[^\"]+", trailer_html)
                    if mp4_match:
                        url = mp4_match.group(0).replace("\\", "")
                        return f"https:{url}" if url.startswith("//") else url

            except Exception as exc:
                self.logger.warning("dmm_fetch_trailer_failed", iframe_url=iframe_url, error=str(exc))
            
        # New format (2025+): onclick="gaEventVideoStart('{&quot;video_url&quot;:&quot;https:\/\/cc3001.dmm.co.jp...&quot;}')"
        # We look for https:\/\/[^&]+.mp4
        match_new = re.search(r"&quot;video_url&quot;:&quot;(https:\\/\\/[^&]+\.mp4)&quot;", html)
        if match_new:
            # We must unescape the JSON slashes
            url = match_new.group(1).replace(r"\/", "/")
            return url
            
        return None

