"""Tests for proxy integration: config validation, credential masking, routing, and failure handling."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from javs.config.models import JavsConfig, ProxyConfig, ScraperConfig
from javs.services.http import (
    CloudflareBlockedError,
    HttpClient,
    InvalidProxyAuthError,
    ProxyConnectionFailedError,
)
from javs.utils.logging import MaskProxyCredentialProcessor


# ─── ProxyConfig Validation Tests ────────────────────────────────────────


class TestProxyConfig:
    """Test ProxyConfig Pydantic model validation."""

    def test_default_config_disabled(self):
        """Default proxy config should be disabled."""
        config = ProxyConfig()
        assert config.enabled is False
        assert config.url == ""
        assert config.timeout_seconds == 15
        assert config.max_retries == 3

    def test_enabled_without_url_raises(self):
        """enabled=True with empty url must raise ValueError."""
        with pytest.raises(ValueError, match="proxy.url is required"):
            ProxyConfig(enabled=True, url="")

    def test_url_without_protocol_raises(self):
        """URL without protocol prefix must raise ValueError."""
        with pytest.raises(ValueError, match="must include protocol"):
            ProxyConfig(url="1.2.3.4:8080")

    def test_valid_http_proxy(self):
        """Valid HTTP proxy URL should pass validation."""
        config = ProxyConfig(enabled=True, url="http://1.2.3.4:8080")
        assert config.enabled is True
        assert config.url == "http://1.2.3.4:8080"

    def test_valid_socks5_proxy(self):
        """Valid SOCKS5 proxy URL should pass validation."""
        config = ProxyConfig(enabled=True, url="socks5://127.0.0.1:10808")
        assert config.enabled is True
        assert config.is_socks is True

    def test_http_proxy_is_not_socks(self):
        """HTTP proxy should not be detected as SOCKS."""
        config = ProxyConfig(enabled=True, url="http://1.2.3.4:8080")
        assert config.is_socks is False

    def test_socks5h_proxy(self):
        """socks5h:// should be detected as SOCKS."""
        config = ProxyConfig(enabled=True, url="socks5h://1.2.3.4:1080")
        assert config.is_socks is True

    def test_disabled_proxy_with_url(self):
        """Disabled proxy with URL should be valid (not active)."""
        config = ProxyConfig(enabled=False, url="http://1.2.3.4:8080")
        assert config.enabled is False


class TestProxyConfigMaskedUrl:
    """Test credential masking in ProxyConfig.masked_url."""

    def test_masked_url_with_auth(self):
        """URL with credentials should have them masked."""
        config = ProxyConfig(
            enabled=True,
            url="http://myuser:mypass@1.2.3.4:8080",
        )
        masked = config.masked_url
        assert "myuser" not in masked
        assert "mypass" not in masked
        assert "***" in masked
        assert "1.2.3.4:8080" in masked

    def test_masked_url_without_auth(self):
        """URL without credentials should remain unchanged."""
        config = ProxyConfig(
            enabled=True,
            url="http://1.2.3.4:8080",
        )
        assert config.masked_url == "http://1.2.3.4:8080"

    def test_masked_url_empty(self):
        """Empty URL should return empty string."""
        config = ProxyConfig()
        assert config.masked_url == ""

    def test_masked_socks5_url_with_auth(self):
        """SOCKS5 URL with auth should be masked."""
        config = ProxyConfig(
            enabled=True,
            url="socks5://user:p@ssw0rd@1.2.3.4:1080",
        )
        masked = config.masked_url
        assert "p@ssw0rd" not in masked
        assert "***" in masked


# ─── ScraperConfig use_proxy Tests ───────────────────────────────────────


class TestScraperConfigUseProxy:
    """Test per-scraper proxy routing configuration."""

    def test_scraper_config_use_proxy_defaults(self):
        """DMM and MGStage should default to use_proxy=True."""
        config = ScraperConfig()
        assert config.use_proxy["dmm"] is True
        assert config.use_proxy["mgstageja"] is True

    def test_other_scrapers_default_no_proxy(self):
        """Non-Japan-blocked scrapers should default to use_proxy=False."""
        config = ScraperConfig()
        assert config.use_proxy["r18dev"] is False
        assert config.use_proxy["javlibrary"] is False
        assert config.use_proxy["javbus"] is False

    def test_full_config_proxy_roundtrip(self):
        """Full JavsConfig with proxy should serialize/deserialize correctly."""
        config = JavsConfig(
            proxy=ProxyConfig(enabled=True, url="socks5://127.0.0.1:10808"),
        )
        assert config.proxy.enabled is True
        assert config.proxy.url == "socks5://127.0.0.1:10808"
        assert config.scrapers.use_proxy["dmm"] is True


# ─── Credential Masking Processor Tests ──────────────────────────────────


class TestMaskProxyCredentialProcessor:
    """Test structlog credential masking processor."""

    def test_masks_exact_url(self):
        """Processor should replace exact raw URL in log event."""
        proc = MaskProxyCredentialProcessor()
        proc.set_proxy_url(
            "http://user:secret@1.2.3.4:8080",
            "http://***:***@1.2.3.4:8080",
        )
        event = {"event": "connection to http://user:secret@1.2.3.4:8080 failed"}
        result = proc(None, "info", event)
        assert "secret" not in result["event"]
        assert "***" in result["event"]

    def test_masks_nested_dict(self):
        """Processor should recursively mask in nested dicts."""
        proc = MaskProxyCredentialProcessor()
        proc.set_proxy_url(
            "socks5://admin:pass123@10.0.0.1:1080",
            "socks5://***:***@10.0.0.1:1080",
        )
        event = {
            "event": "test",
            "details": {
                "proxy": "socks5://admin:pass123@10.0.0.1:1080",
                "status": "failed",
            },
        }
        result = proc(None, "error", event)
        assert "pass123" not in str(result)
        assert "admin" not in str(result)

    def test_regex_fallback_masks_unknown_urls(self):
        """Regex fallback should mask any userinfo pattern in proxy URLs."""
        proc = MaskProxyCredentialProcessor()
        # No set_proxy_url called — regex fallback only
        event = {"event": "error at http://leaked:password@5.6.7.8:3128"}
        result = proc(None, "error", event)
        assert "leaked" not in result["event"]
        assert "password" not in result["event"]

    def test_no_mask_when_no_proxy(self):
        """Processor without proxy URL should pass through unchanged."""
        proc = MaskProxyCredentialProcessor()
        event = {"event": "normal log message", "url": "http://example.com"}
        result = proc(None, "info", event)
        assert result["event"] == "normal log message"
        assert result["url"] == "http://example.com"


# ─── HttpClient Proxy Tests ─────────────────────────────────────────────


class TestHttpClientProxy:
    """Test HttpClient proxy configuration and routing."""

    def test_socks_connector_created(self):
        """SOCKS5 proxy should use ProxyConnector."""
        client = HttpClient(proxy_url="socks5://127.0.0.1:10808")
        assert client._is_socks is True

    def test_http_proxy_not_socks(self):
        """HTTP proxy should not use SOCKS connector."""
        client = HttpClient(proxy_url="http://1.2.3.4:8080")
        assert client._is_socks is False

    def test_no_proxy_default(self):
        """No proxy URL should result in no proxy configuration."""
        client = HttpClient()
        assert client._proxy_url is None
        assert client._is_socks is False

    def test_proxy_masked_url(self):
        """Proxy URL with auth should have masked version."""
        client = HttpClient(proxy_url="http://user:pass@1.2.3.4:8080")
        assert client._proxy_masked is not None
        assert "pass" not in client._proxy_masked
        assert "***" in client._proxy_masked

    def test_get_proxy_kwargs_http(self):
        """HTTP proxy should produce per-request proxy kwarg."""
        client = HttpClient(proxy_url="http://1.2.3.4:8080")
        kwargs = client._get_proxy_kwargs(use_proxy=True)
        assert kwargs == {"proxy": "http://1.2.3.4:8080"}

    def test_get_proxy_kwargs_socks(self):
        """SOCKS proxy should return empty dict (handled at connector level)."""
        client = HttpClient(proxy_url="socks5://127.0.0.1:10808")
        kwargs = client._get_proxy_kwargs(use_proxy=True)
        assert kwargs == {}

    def test_get_proxy_kwargs_disabled(self):
        """use_proxy=False should return empty dict."""
        client = HttpClient(proxy_url="http://1.2.3.4:8080")
        kwargs = client._get_proxy_kwargs(use_proxy=False)
        assert kwargs == {}

    def test_get_proxy_kwargs_no_proxy_configured(self):
        """No proxy configured should return empty dict."""
        client = HttpClient()
        kwargs = client._get_proxy_kwargs(use_proxy=True)
        assert kwargs == {}

    def test_sanitize_error_masks_proxy_url(self):
        """Error sanitization should replace raw proxy URL."""
        client = HttpClient(proxy_url="http://user:pass@1.2.3.4:8080")
        exc = Exception("Cannot connect to http://user:pass@1.2.3.4:8080")
        sanitized = client._sanitize_error(exc)
        assert "pass" not in sanitized
        assert "***" in sanitized


class TestHttpClient407Handling:
    """Test HTTP 407 Proxy Authentication Required handling."""

    def test_check_proxy_status_407(self):
        """407 response should raise InvalidProxyAuthError."""
        client = HttpClient(proxy_url="http://user:pass@1.2.3.4:8080")
        mock_resp = MagicMock()
        mock_resp.status = 407
        with pytest.raises(InvalidProxyAuthError, match="407"):
            client._check_proxy_status(mock_resp)

    def test_check_proxy_status_200_ok(self):
        """200 response should not raise anything."""
        client = HttpClient(proxy_url="http://user:pass@1.2.3.4:8080")
        mock_resp = MagicMock()
        mock_resp.status = 200
        # Should not raise
        client._check_proxy_status(mock_resp)

    def test_check_proxy_status_403_ok(self):
        """403 response should not trigger proxy auth error (it's a target error)."""
        client = HttpClient(proxy_url="http://user:pass@1.2.3.4:8080")
        mock_resp = MagicMock()
        mock_resp.status = 403
        # Should not raise (403 is a target-level error, not proxy auth)
        client._check_proxy_status(mock_resp)
