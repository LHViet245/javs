import asyncio
import sys

import yaml

from javs.scrapers.javlibrary import JavlibraryScraper
from javs.services.http import HttpClient


async def main():
    print("Testing JavlibraryScraper with HNTRZ-015...")

    # Load config mapping CF cookie and User-Agent
    with open("javs/data/default_config.yaml") as f:
        config = yaml.safe_load(f)

    cf_config = config.get("cloudflare", {})
    cf_clearance = cf_config.get("cf_clearance")
    user_agent = cf_config.get("user_agent")

    print(f"Using CF Clearance ending in: {cf_clearance[-10:] if cf_clearance else 'None'}")

    http = HttpClient(cf_clearance=cf_clearance, cf_user_agent=user_agent)
    scraper = JavlibraryScraper(http=http)

    try:
        print("1. Searching for HNTRZ-015...")
        url = await scraper.search("HNTRZ-015")

        if not url:
            print("FAIL: Search returned None.")
            sys.exit(1)

        print(f"2. Search success! URL: {url}")
        print("3. Scraping movie data...")

        data = await scraper.scrape(url)

        if not data:
            print("FAIL: Scrape returned None.")
            sys.exit(1)

        print("\n=== Scrape Results ===")
        print(f"  ID:           {data.id}")
        print(f"  Title:        {data.title}")
        print(f"  Release Date: {data.release_date}")
        print(f"  Runtime:      {data.runtime} min")
        print(f"  Director:     {data.director}")
        print(f"  Maker:        {data.maker}")
        print(f"  Label:        {data.label}")
        print(f"  Rating:       {data.rating}")
        print(f"  Cover URL:    {data.cover_url}")
        print(f"  Genres:       {data.genres}")
        print(f"  Actresses:    {[a.full_name for a in data.actresses]}")
        print(f"  Screenshots:  {len(data.screenshot_urls)} found")
        print(f"  Source:       {data.source}")
        print("\nSUCCESS: All fields scraped!")
    finally:
        await scraper.http.close()


if __name__ == "__main__":
    asyncio.run(main())
