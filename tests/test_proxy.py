"""Tests for proxy: config validation, credential masking, routing, failure."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from javs.config.models import JavsConfig, ProxyConfig, ScraperConfig
from javs.services.http import (
    HttpClient,
    InvalidProxyAuthError,
    ProxyConnectionFailedError,
)
from javs.services.proxy_diagnostics import ProxyDiagnosticResult, run_proxy_diagnostics
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


class TestHttpClientRetryConfig:
    """Test that retry behavior honors runtime configuration."""

    @pytest.mark.asyncio
    async def test_get_honors_configured_max_retries(self, monkeypatch):
        """get() should retry exactly max_retries times before failing."""
        client = HttpClient(max_retries=5)
        attempts = {"count": 0}

        class BoomSession:
            def get(self, *args, **kwargs):
                attempts["count"] += 1
                raise RuntimeError("proxy unreachable")

        async def fake_get_session(use_proxy: bool = False):
            return BoomSession()

        monkeypatch.setattr(client, "_get_session", fake_get_session)

        with pytest.raises(ProxyConnectionFailedError):
            await client.get("https://example.com", use_proxy=True)

        assert attempts["count"] == 5

    @pytest.mark.asyncio
    async def test_get_json_honors_configured_max_retries(self, monkeypatch):
        """get_json() should retry exactly max_retries times before failing."""
        client = HttpClient(max_retries=4)
        attempts = {"count": 0}

        class BoomSession:
            def get(self, *args, **kwargs):
                attempts["count"] += 1
                raise RuntimeError("proxy unreachable")

        async def fake_get_session(use_proxy: bool = False):
            return BoomSession()

        monkeypatch.setattr(client, "_get_session", fake_get_session)

        with pytest.raises(ProxyConnectionFailedError):
            await client.get_json("https://example.com/api", use_proxy=True)

        assert attempts["count"] == 4

    @pytest.mark.asyncio
    async def test_get_proxy_failure_never_leaks_raw_proxy_credentials(self, monkeypatch):
        """Raised proxy failures should expose only sanitized proxy text."""
        raw_proxy = "http://user:secret@1.2.3.4:8080"
        client = HttpClient(proxy_url=raw_proxy, max_retries=1)

        class BoomSession:
            def get(self, *args, **kwargs):
                del args, kwargs
                raise RuntimeError(f"proxy unreachable via {raw_proxy}")

        async def fake_get_session(use_proxy: bool = False):
            del use_proxy
            return BoomSession()

        monkeypatch.setattr(client, "_get_session", fake_get_session)

        with pytest.raises(ProxyConnectionFailedError) as excinfo:
            await client.get("https://example.com", use_proxy=True)

        message = str(excinfo.value)
        assert "secret" not in message
        assert "user" not in message
        assert "***" in message


class TestProxyDiagnostics:
    """Test proxy diagnostics helper behavior."""

    @pytest.mark.asyncio
    async def test_run_proxy_diagnostics_reports_success(self, monkeypatch):
        """Diagnostics should report success when a proxied request succeeds."""
        config = JavsConfig()
        config.proxy.enabled = True
        config.proxy.url = "http://1.2.3.4:8080"
        config.proxy.timeout_seconds = 9
        captured: dict[str, object] = {}

        class DummyHttpClient:
            def __init__(self, **kwargs) -> None:
                captured.update(kwargs)

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb) -> None:
                return None

            async def get(self, url: str, use_proxy: bool = False) -> str:
                captured["url"] = url
                captured["use_proxy"] = use_proxy
                return "ok"

        monkeypatch.setattr("javs.services.proxy_diagnostics.HttpClient", DummyHttpClient)
        monkeypatch.setattr("javs.services.proxy_diagnostics.PROXY_TEST_URL", "https://probe.test")

        result = await run_proxy_diagnostics(config)

        assert result == ProxyDiagnosticResult(ok=True, message="Proxy reachable")
        assert captured["proxy_url"] == "http://1.2.3.4:8080"
        assert captured["timeout_seconds"] == 9
        assert captured["url"] == "https://probe.test"
        assert captured["use_proxy"] is True

    @pytest.mark.asyncio
    async def test_run_proxy_diagnostics_reports_disabled_proxy(self):
        """Diagnostics should fail fast when proxy support is disabled."""
        result = await run_proxy_diagnostics(JavsConfig())

        assert result.ok is False
        assert result.message == "Proxy is disabled in config"


class _DummySession:
    def __init__(self, connector) -> None:
        self.connector = connector
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class TestHttpClientSessionRouting:
    """Test direct/proxy session selection."""

    @pytest.mark.asyncio
    async def test_socks_proxy_uses_separate_direct_and_proxy_sessions(self, monkeypatch):
        """SOCKS proxy routing should keep direct requests off the proxy session."""
        client = HttpClient(proxy_url="socks5://127.0.0.1:10808")
        created_sessions: list[_DummySession] = []

        monkeypatch.setattr(client, "_create_connector", lambda: "proxy-connector")
        monkeypatch.setattr(
            "javs.services.http.aiohttp.TCPConnector",
            lambda **kwargs: "direct-connector",
        )

        def fake_client_session(*, connector, timeout, headers):
            session = _DummySession(connector)
            created_sessions.append(session)
            return session

        monkeypatch.setattr("javs.services.http.aiohttp.ClientSession", fake_client_session)

        direct = await client._get_session(use_proxy=False)
        proxy = await client._get_session(use_proxy=True)

        assert direct.connector == "direct-connector"
        assert proxy.connector == "proxy-connector"
        assert direct is not proxy
        assert len(created_sessions) == 2

    @pytest.mark.asyncio
    async def test_http_proxy_uses_proxy_session_only_when_requested(self, monkeypatch):
        """HTTP proxy routing should keep a dedicated proxy session separate from direct traffic."""
        client = HttpClient(proxy_url="http://1.2.3.4:8080")
        created_sessions: list[_DummySession] = []

        monkeypatch.setattr(client, "_create_connector", lambda: "proxy-http-connector")
        monkeypatch.setattr(
            "javs.services.http.aiohttp.TCPConnector",
            lambda **kwargs: "direct-http-connector",
        )

        def fake_client_session(*, connector, timeout, headers):
            session = _DummySession(connector)
            created_sessions.append(session)
            return session

        monkeypatch.setattr("javs.services.http.aiohttp.ClientSession", fake_client_session)

        direct = await client._get_session(use_proxy=False)
        proxy = await client._get_session(use_proxy=True)

        assert direct.connector == "direct-http-connector"
        assert proxy.connector == "proxy-http-connector"
        assert direct is not proxy
        assert len(created_sessions) == 2

    @pytest.mark.asyncio
    async def test_close_closes_both_direct_and_proxy_sessions_and_resets_state(self):
        """close() should shut down both sessions and clear cached handles."""
        client = HttpClient(proxy_url="http://1.2.3.4:8080")
        direct = _DummySession("direct")
        proxy = _DummySession("proxy")
        client._session_direct = direct
        client._session_proxy = proxy

        await client.close()

        assert direct.closed is True
        assert proxy.closed is True
        assert client._session_direct is None
        assert client._session_proxy is None


class _FakeContent:
    def __init__(self, chunks: Sequence[bytes]) -> None:
        self._chunks = chunks

    async def iter_chunked(self, _: int):
        for chunk in self._chunks:
            yield chunk


class _FailingContent:
    def __init__(self, chunks: Sequence[bytes], error: Exception) -> None:
        self._chunks = chunks
        self._error = error

    async def iter_chunked(self, _: int):
        for chunk in self._chunks:
            yield chunk
        raise self._error


class _YieldingContent:
    def __init__(self, chunks: Sequence[bytes]) -> None:
        self._chunks = chunks

    async def iter_chunked(self, _: int):
        for chunk in self._chunks:
            await asyncio.sleep(0)
            yield chunk


class _FakeResponse:
    def __init__(
        self,
        *,
        text_value: str = "ok",
        json_value: dict | None = None,
        chunks: Sequence[bytes] = (),
        content: _FakeContent | _FailingContent | _YieldingContent | None = None,
    ) -> None:
        self.status = 200
        self._text_value = text_value
        self._json_value = json_value or {"ok": True}
        self.content = content or _FakeContent(chunks)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    async def text(self) -> str:
        return self._text_value

    async def json(self, content_type=None) -> dict:
        return self._json_value


class _FakeSession:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.calls: list[dict[str, object]] = []

    def get(self, *args, **kwargs) -> _FakeResponse:
        self.calls.append({"args": args, "kwargs": kwargs})
        return self._response


class _RaisingSession:
    def __init__(self, error: Exception) -> None:
        self._error = error
        self.calls: list[dict[str, object]] = []

    def get(self, *args, **kwargs) -> _FakeResponse:
        self.calls.append({"args": args, "kwargs": kwargs})
        raise self._error


class TestHttpClientSslSemantics:
    """Test verify_ssl maps directly to aiohttp's ssl kwarg."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("verify_ssl", [True, False])
    async def test_get_uses_verify_ssl_value(self, monkeypatch, verify_ssl: bool):
        client = HttpClient(verify_ssl=verify_ssl)
        session = _FakeSession(_FakeResponse(text_value="body"))

        async def fake_get_session(use_proxy: bool = False):
            return session

        monkeypatch.setattr(client, "_get_session", fake_get_session)

        body = await client.get("https://example.com")

        assert body == "body"
        assert session.calls[0]["kwargs"]["ssl"] is verify_ssl

    @pytest.mark.asyncio
    @pytest.mark.parametrize("verify_ssl", [True, False])
    async def test_get_json_uses_verify_ssl_value(self, monkeypatch, verify_ssl: bool):
        client = HttpClient(verify_ssl=verify_ssl)
        session = _FakeSession(_FakeResponse(json_value={"movie": "ABP-420"}))

        async def fake_get_session(use_proxy: bool = False):
            return session

        monkeypatch.setattr(client, "_get_session", fake_get_session)

        payload = await client.get_json("https://example.com/api")

        assert payload == {"movie": "ABP-420"}
        assert session.calls[0]["kwargs"]["ssl"] is verify_ssl

    @pytest.mark.asyncio
    @pytest.mark.parametrize("verify_ssl", [True, False])
    async def test_download_uses_verify_ssl_value(self, monkeypatch, tmp_path, verify_ssl: bool):
        client = HttpClient(verify_ssl=verify_ssl)
        session = _FakeSession(_FakeResponse(chunks=[b"poster-bytes"]))

        async def fake_get_session(use_proxy: bool = False):
            return session

        monkeypatch.setattr(client, "_get_session", fake_get_session)
        dest = Path(tmp_path / "cover.jpg")

        ok = await client.download("https://example.com/cover.jpg", dest)

        assert ok is True
        assert dest.read_bytes() == b"poster-bytes"
        assert session.calls[0]["kwargs"]["ssl"] is verify_ssl

    @pytest.mark.asyncio
    async def test_download_creates_nested_parent_and_writes_all_chunks(
        self, monkeypatch, tmp_path
    ) -> None:
        client = HttpClient()
        session = _FakeSession(_FakeResponse(chunks=[b"poster-", b"bytes"]))

        async def fake_get_session(use_proxy: bool = False):
            return session

        monkeypatch.setattr(client, "_get_session", fake_get_session)
        dest = tmp_path / "nested" / "images" / "cover.jpg"

        ok = await client.download("https://example.com/cover.jpg", dest)

        assert ok is True
        assert dest.read_bytes() == b"poster-bytes"
        assert not dest.with_name("cover.jpg.part").exists()

    @pytest.mark.asyncio
    async def test_download_returns_false_when_request_setup_fails(
        self, monkeypatch, tmp_path
    ) -> None:
        client = HttpClient()
        session = _RaisingSession(RuntimeError("boom"))

        async def fake_get_session(use_proxy: bool = False):
            return session

        monkeypatch.setattr(client, "_get_session", fake_get_session)
        dest = tmp_path / "cover.jpg"

        ok = await client.download("https://example.com/cover.jpg", dest)

        assert ok is False
        assert not dest.exists()
        assert not dest.with_name("cover.jpg.part").exists()

    @pytest.mark.asyncio
    async def test_download_cleans_partial_file_when_stream_fails(
        self, monkeypatch, tmp_path
    ) -> None:
        client = HttpClient()
        response = _FakeResponse(
            content=_FailingContent([b"partial-bytes"], RuntimeError("stream failed"))
        )
        session = _FakeSession(response)

        async def fake_get_session(use_proxy: bool = False):
            return session

        monkeypatch.setattr(client, "_get_session", fake_get_session)
        dest = tmp_path / "posters" / "cover.jpg"

        ok = await client.download("https://example.com/cover.jpg", dest)

        assert ok is False
        assert not dest.exists()
        assert not dest.with_name("cover.jpg.part").exists()

    @pytest.mark.asyncio
    async def test_download_and_close_complete_without_background_task_hang(
        self, monkeypatch, tmp_path
    ) -> None:
        client = HttpClient()
        response = _FakeResponse(content=_YieldingContent([b"a", b"b", b"c"]))
        session = _FakeSession(response)

        async def fake_get_session(use_proxy: bool = False):
            return session

        monkeypatch.setattr(client, "_get_session", fake_get_session)
        dest = tmp_path / "cover.jpg"

        ok = await asyncio.wait_for(
            client.download("https://example.com/cover.jpg", dest),
            timeout=1,
        )

        assert ok is True
        assert dest.read_bytes() == b"abc"
        await asyncio.wait_for(client.close(), timeout=1)


class TestCloudflareManualConfig:
    """Test Cloudflare manual-cookie wiring."""

    @pytest.mark.asyncio
    async def test_get_cf_prefers_manual_cookie_and_user_agent(self, monkeypatch):
        """Configured cf_clearance should route through HttpClient.get() with merged headers."""
        client = HttpClient(cf_clearance="cf-cookie", cf_user_agent="My Browser UA")
        captured: dict[str, object] = {}

        async def fake_get(
            url: str,
            headers: dict[str, str] | None = None,
            cookies: dict[str, str] | None = None,
            params: dict[str, str] | None = None,
            allow_redirects: bool = True,
            use_proxy: bool = False,
        ) -> str:
            captured["url"] = url
            captured["headers"] = headers or {}
            captured["cookies"] = cookies or {}
            captured["params"] = params or {}
            captured["allow_redirects"] = allow_redirects
            captured["use_proxy"] = use_proxy
            return "manual-body"

        monkeypatch.setattr(client, "get", fake_get)

        body = await client.get_cf(
            "https://www.javlibrary.com/en/?v=javme12345",
            headers={"Referer": "https://www.javlibrary.com"},
            cookies={"session": "existing-cookie"},
            params={"foo": "bar"},
            use_proxy=True,
        )

        assert body == "manual-body"
        assert captured["url"] == "https://www.javlibrary.com/en/?v=javme12345"
        assert captured["headers"]["User-Agent"] == "My Browser UA"
        assert captured["headers"]["Referer"] == "https://www.javlibrary.com"
        assert captured["cookies"]["cf_clearance"] == "cf-cookie"
        assert captured["cookies"]["session"] == "existing-cookie"
        assert captured["params"] == {"foo": "bar"}
        assert captured["use_proxy"] is True
