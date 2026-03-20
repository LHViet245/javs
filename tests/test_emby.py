"""Tests for the Emby/Jellyfin client."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from javs.config.models import EmbyConfig
from javs.services.emby import EmbyClient


class TestEmbyClient:
    """Verify Emby client request wiring and failure handling."""

    def setup_method(self) -> None:
        self.config = EmbyConfig(url="http://emby.local:8096/", api_key="secret-key")

    @pytest.mark.asyncio
    async def test_get_persons_returns_items_from_response(self) -> None:
        http = AsyncMock()
        http.get_json.return_value = {"Items": [{"Id": "1"}, {"Id": "2"}]}
        client = EmbyClient(self.config, http=http)

        persons = await client.get_persons()

        assert persons == [{"Id": "1"}, {"Id": "2"}]
        http.get_json.assert_awaited_once_with(
            "http://emby.local:8096/Persons",
            params={"api_key": "secret-key"},
        )

    @pytest.mark.asyncio
    async def test_get_persons_returns_empty_list_on_error(self) -> None:
        http = AsyncMock()
        http.get_json.side_effect = RuntimeError("boom")
        client = EmbyClient(self.config, http=http)

        persons = await client.get_persons()

        assert persons == []

    @pytest.mark.asyncio
    async def test_set_person_thumb_triggers_remote_download(self) -> None:
        http = AsyncMock()
        client = EmbyClient(self.config, http=http)

        ok = await client.set_person_thumb("person-1", "https://example.com/thumb.jpg")

        assert ok is True
        http.get.assert_awaited_once_with(
            "http://emby.local:8096/Items/person-1/RemoteImages/Download",
            params={
                "api_key": "secret-key",
                "Type": "Primary",
                "ImageUrl": "https://example.com/thumb.jpg",
            },
        )

    @pytest.mark.asyncio
    async def test_set_person_thumb_returns_false_on_error(self) -> None:
        http = AsyncMock()
        http.get.side_effect = RuntimeError("boom")
        client = EmbyClient(self.config, http=http)

        ok = await client.set_person_thumb("person-1", "https://example.com/thumb.jpg")

        assert ok is False

    @pytest.mark.asyncio
    async def test_scan_library_hits_refresh_endpoint(self) -> None:
        http = AsyncMock()
        client = EmbyClient(self.config, http=http)

        ok = await client.scan_library()

        assert ok is True
        http.get.assert_awaited_once_with(
            "http://emby.local:8096/Library/Refresh",
            params={"api_key": "secret-key"},
        )

    @pytest.mark.asyncio
    async def test_scan_library_returns_false_on_error(self) -> None:
        http = AsyncMock()
        http.get.side_effect = RuntimeError("boom")
        client = EmbyClient(self.config, http=http)

        ok = await client.scan_library()

        assert ok is False
