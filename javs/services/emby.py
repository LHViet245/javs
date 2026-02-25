"""Emby/Jellyfin API client for media server integration.

Replaces Javinizer's Emby-related cmdlets.
"""

from __future__ import annotations

from javs.config.models import EmbyConfig
from javs.services.http import HttpClient
from javs.utils.logging import get_logger

logger = get_logger(__name__)


class EmbyClient:
    """Client for Emby/Jellyfin API operations.

    Supports:
    - Setting/replacing actress thumbnails
    - Triggering library scans
    """

    def __init__(self, config: EmbyConfig, http: HttpClient | None = None) -> None:
        self.config = config
        self.http = http or HttpClient()
        self.base_url = config.url.rstrip("/")
        self.api_key = config.api_key

    async def get_persons(self) -> list[dict]:
        """Get all persons (actors/actresses) from the server.

        Returns:
            List of person records.
        """
        url = f"{self.base_url}/Persons"
        params = {"api_key": self.api_key}
        try:
            data = await self.http.get_json(url, params=params)
            return data.get("Items", [])
        except Exception as exc:
            logger.error("emby_get_persons_error", error=str(exc))
            return []

    async def set_person_thumb(
        self,
        person_id: str,
        image_url: str,
    ) -> bool:
        """Set a person's thumbnail image.

        Args:
            person_id: Emby/Jellyfin person ID.
            image_url: URL of the thumbnail image.

        Returns:
            True if successful.
        """
        url = f"{self.base_url}/Items/{person_id}/RemoteImages/Download"
        params = {
            "api_key": self.api_key,
            "Type": "Primary",
            "ImageUrl": image_url,
        }
        try:
            await self.http.get(url, params=params)
            logger.debug("emby_thumb_set", person_id=person_id)
            return True
        except Exception as exc:
            logger.error("emby_thumb_error", person_id=person_id, error=str(exc))
            return False

    async def scan_library(self) -> bool:
        """Trigger a library scan.

        Returns:
            True if scan was triggered.
        """
        url = f"{self.base_url}/Library/Refresh"
        params = {"api_key": self.api_key}
        try:
            await self.http.get(url, params=params)
            logger.info("emby_scan_triggered")
            return True
        except Exception as exc:
            logger.error("emby_scan_error", error=str(exc))
            return False
