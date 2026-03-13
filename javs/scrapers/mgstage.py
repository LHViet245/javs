"""Mgstage scraper."""

from __future__ import annotations

import re
from typing import ClassVar

from bs4 import BeautifulSoup

from javs.models.movie import Actress, MovieData, Rating
from javs.scrapers.base import BaseScraper
from javs.scrapers.registry import ScraperRegistry
from javs.utils.string import clean_title


@ScraperRegistry.register
class MgstageJaScraper(BaseScraper):
    name: ClassVar[str] = "mgstageja"
    display_name: ClassVar[str] = "MGStage (JA)"
    languages: ClassVar[list[str]] = ["ja"]
    base_url: ClassVar[str] = "https://www.mgstage.com"

    async def search(self, movie_id: str) -> str | None:
        """Search for a movie ID and return the exact detail URL."""
        # Search URL
        search_url = f"{self.base_url}/search/cSearch.php?search_word={movie_id}"

        try:
            # We must use cookies={"adc": "1"} to bypass age gates
            html = await self.http.get(
                search_url,
                cookies={"adc": "1"},
                use_proxy=self.use_proxy,
            )
        except Exception as e:
            self.logger.warning("search_request_failed", url=search_url, error=str(e))
            return None

        soup = BeautifulSoup(html, "lxml")

        # In MGStage, results are usually inside .search_list
        search_results = soup.select(".search_list a[href^='/product/product_detail/']")
        if not search_results:
            return await self._fallback_prefixes(movie_id)

        # To be accurate, we try to match the movie ID in the URL.
        # MGStage URLs look like: /product/product_detail/406FSDSS-198/
        c_id = movie_id.upper().replace("-", "")
        for btn in search_results:
            href = btn.get("href", "")
            if href:
                clean_href = href.strip("/")
                part_id = clean_href.split("/")[-1].upper()

                # Check if the requested ID is in the parsed URL's product_id
                part_id_no_dash = part_id.replace("-", "")
                if c_id in part_id_no_dash:
                    full_url = f"{self.base_url}{href}"
                    # Ensure trailing slash for uniformity
                    if not full_url.endswith("/"):
                        full_url += "/"
                    return full_url

        # Fallback to the first result
        first_href = search_results[0].get("href", "")
        if first_href:
            full_url = f"{self.base_url}{first_href}"
            if not full_url.endswith("/"):
                full_url += "/"
            return full_url

        return None

    async def _fallback_prefixes(self, movie_id: str) -> str | None:
        """Try direct GET with common MGStage publisher prefixes."""
        import asyncio

        # Common studio prefixes: Prestige (406, 300, 118, 428), FALENO (336), KMP (348), SOD (259, 228), Giga (200), TMA (436, 480)
        prefixes = ["406", "336", "348", "259", "200", "300", "118", "129", "459", "436", "480", "428", "228"]
        c_id = movie_id.upper()
        
        async def check_url(url: str) -> str | None:
            try:
                resp = await self.http.get(url, cookies={"adc": "1"}, use_proxy=self.use_proxy)
                if c_id in resp:
                    return url
                return None
            except Exception:
                return None
                
        tasks = [check_url(f"{self.base_url}/product/product_detail/{p}{c_id}/") for p in prefixes]
        results = await asyncio.gather(*tasks)
        for r in results:
            if r:
                return r
        return None

    async def scrape(self, url: str) -> MovieData | None:
        """Scrape metadata from a MGStage detail page."""
        try:
            html = await self.http.get(
                url,
                cookies={"adc": "1"},
                use_proxy=self.use_proxy,
            )
        except Exception as e:
            self.logger.warning("scrape_request_failed", url=url, error=str(e))
            return None

        soup = BeautifulSoup(html, "lxml")

        title = ""
        title_tag = soup.find("title")
        if title_tag:
            title = clean_title(title_tag.text.strip())

        def get_td_text(th_text: str) -> str:
            th = soup.find("th", string=re.compile(th_text))
            if th and th.find_next_sibling("td"):
                return th.find_next_sibling("td").text.strip()
            return ""

        d_id = get_td_text("品番：")

        description = ""
        desc_p = soup.select_one("p.txt.introduction")
        if desc_p:
            description = desc_p.text.strip()

        release_date = get_td_text("配信開始日：")
        if release_date:
            release_date = release_date.replace("/", "-")

        runtime_str = get_td_text("収録時間：")
        runtime_min = None
        if runtime_str:
            match = re.search(r"(\d+)", runtime_str)
            if match:
                runtime_min = int(match.group(1))

        maker = get_td_text("メーカー：")
        label = get_td_text("レーベル：")
        series = get_td_text("シリーズ：")

        rating = None
        rating_span = soup.select_one("span[class^='star_']")
        if rating_span:
            cls_name = rating_span.get("class", [""])[0]
            m = re.search(r"star_(\d+)", cls_name)
            if m:
                # mgstage stars: 45 means 4.5. Scale to 10 points -> 4.5 * 2 = 9
                try:
                    stars = float(m.group(1)) / 10.0
                    rating = Rating(rating=round(stars * 2, 2))
                except ValueError:
                    pass

        genres = []
        genre_th = soup.find("th", string=re.compile("ジャンル："))
        if genre_th and genre_th.find_next_sibling("td"):
            for a in genre_th.find_next_sibling("td").find_all("a"):
                g = a.text.strip()
                if g:
                    genres.append(g)

        actresses = []
        actress_th = soup.find("th", string=re.compile("出演："))
        if actress_th and actress_th.find_next_sibling("td"):
            for a in actress_th.find_next_sibling("td").find_all("a"):
                raw_name = a.text.strip()
                if not raw_name:
                    continue
                # Check if it has Japanese chars
                if re.search(r"[\u3040-\u309f\u30a0-\u30ff\uff66-\uff9f\u4e00-\u9faf]", raw_name):
                    actresses.append(Actress(japanese_name=raw_name))
                else:
                    parts = raw_name.split()
                    if len(parts) >= 2:
                        actresses.append(
                            Actress(first_name=parts[0], last_name=" ".join(parts[1:]))
                        )
                    else:
                        actresses.append(Actress(first_name=raw_name))

        cover_url = ""
        cover_a = soup.select_one("a.link_magnify")
        if cover_a and cover_a.get("href"):
            cover_url = cover_a.get("href")

        screenshots = []
        for a in soup.select("a.sample_image"):
            if a.get("href"):
                screenshots.append(a.get("href"))

        trailer_url = ""
        sample_el = soup.select_one("a.button_sample[href*='sampleplayer.html']") or soup.select_one("a[href*='sampleplayer.html']") or soup.select_one("iframe[src*='sampleplayer.html']")
        if sample_el:
            src = sample_el.get("href") or sample_el.get("src") or ""
            pid_match = re.search(r"sampleplayer\.html/([^/]+)", src)
            if pid_match:
                pid = pid_match.group(1)
                req_url = f"{self.base_url}/sampleplayer/sampleRespons.php?pid={pid}"
                try:
                    trailer_resp = await self.http.get(
                        req_url,
                        cookies={"adc": "1"},
                        use_proxy=self.use_proxy,
                    )
                    t_match = re.search(r'(https[^"\'\s]+\.ism)\\/', trailer_resp)
                    if t_match:
                        clean_url = t_match.group(1).replace("\\/", "/")
                        trailer_url = clean_url.replace(".ism", ".mp4")
                except Exception as e:
                    self.logger.debug("trailer_fetch_failed", error=str(e))

        if not d_id:
            return None

        return MovieData(
            id=d_id,
            title=title,
            description=description,
            release_date=release_date,
            runtime=runtime_min,
            maker=maker,
            label=label,
            series=series,
            genres=genres,
            actresses=actresses,
            cover_url=cover_url,
            screenshots=screenshots,
            trailer_url=trailer_url,
            rating=rating,
            source=self.name,
            url=url,
        )
