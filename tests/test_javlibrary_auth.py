"""Tests for Javlibrary credential prompt and validation helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from javs.config.models import JavsConfig
from javs.services.http import CloudflareBlockedError
from javs.services.javlibrary_auth import (
    JavlibraryCredentials,
    apply_javlibrary_credentials,
    configure_javlibrary_credentials,
    print_cloudflare_guidance,
    prompt_for_javlibrary_credentials,
    validate_javlibrary_credentials,
)


class TestConfigureJavlibraryCredentials:
    @pytest.mark.asyncio
    async def test_configure_saves_credentials_after_success(self, monkeypatch, tmp_path: Path):
        config = JavsConfig()
        saved: list[Path] = []

        monkeypatch.setattr(
            "javs.services.javlibrary_auth.prompt_for_javlibrary_credentials",
            lambda existing=None: JavlibraryCredentials("cf-cookie", "browser-ua"),
        )
        async def fake_validate(*_args, **_kwargs) -> None:
            return None

        monkeypatch.setattr(
            "javs.services.javlibrary_auth.validate_javlibrary_credentials",
            fake_validate,
        )
        monkeypatch.setattr(
            "javs.services.javlibrary_auth.save_config",
            lambda _cfg, path=None: saved.append(path),
        )

        credentials = await configure_javlibrary_credentials(
            config,
            tmp_path / "config.yaml",
            prompt_on_missing=False,
            send_notification=False,
            save_on_success=True,
        )

        assert credentials == JavlibraryCredentials("cf-cookie", "browser-ua")
        assert config.javlibrary.cookie_cf_clearance == "cf-cookie"
        assert config.javlibrary.browser_user_agent == "browser-ua"
        assert saved == [tmp_path / "config.yaml"]

    @pytest.mark.asyncio
    async def test_configure_does_not_save_when_validation_fails(
        self, monkeypatch, tmp_path: Path
    ):
        config = JavsConfig()
        saved: list[Path] = []

        monkeypatch.setattr(
            "javs.services.javlibrary_auth.prompt_for_javlibrary_credentials",
            lambda existing=None: JavlibraryCredentials("bad-cookie", "browser-ua"),
        )

        async def fail_validate(*_args, **_kwargs):
            raise CloudflareBlockedError("blocked")

        monkeypatch.setattr(
            "javs.services.javlibrary_auth.validate_javlibrary_credentials",
            fail_validate,
        )
        monkeypatch.setattr(
            "javs.services.javlibrary_auth.save_config",
            lambda _cfg, path=None: saved.append(path),
        )

        credentials = await configure_javlibrary_credentials(
            config,
            tmp_path / "config.yaml",
            prompt_on_missing=False,
            send_notification=False,
            save_on_success=True,
        )

        assert credentials is None
        assert config.javlibrary.cookie_cf_clearance == ""
        assert config.javlibrary.browser_user_agent == ""
        assert saved == []


class TestPromptForJavlibraryCredentials:
    def test_reuses_saved_user_agent_without_prompting_for_it(self, monkeypatch) -> None:
        prompts: list[str] = []

        def fake_prompt(text: str, **_kwargs) -> str:
            prompts.append(text)
            return "new-cf-cookie"

        monkeypatch.setattr("typer.prompt", fake_prompt)

        credentials = prompt_for_javlibrary_credentials(
            JavlibraryCredentials("old-cookie", "saved-browser-ua")
        )

        assert credentials == JavlibraryCredentials("new-cf-cookie", "saved-browser-ua")
        assert prompts == ["Javlibrary cf_clearance"]

    def test_prompts_for_user_agent_when_not_saved(self, monkeypatch) -> None:
        prompts: list[str] = []

        def fake_prompt(text: str, **_kwargs) -> str:
            prompts.append(text)
            if text == "Javlibrary cf_clearance":
                return "new-cf-cookie"
            return "new-browser-ua"

        monkeypatch.setattr("typer.prompt", fake_prompt)

        credentials = prompt_for_javlibrary_credentials(
            JavlibraryCredentials("old-cookie", "")
        )

        assert credentials == JavlibraryCredentials("new-cf-cookie", "new-browser-ua")
        assert prompts == [
            "Javlibrary cf_clearance",
            "Javlibrary browser User-Agent",
        ]


def test_apply_javlibrary_credentials_updates_config() -> None:
    config = JavsConfig()

    apply_javlibrary_credentials(config, JavlibraryCredentials("cf-cookie", "browser-ua"))

    assert config.javlibrary.cookie_cf_clearance == "cf-cookie"
    assert config.javlibrary.browser_user_agent == "browser-ua"


@pytest.mark.asyncio
async def test_validate_javlibrary_credentials_reads_use_proxy_from_dict(monkeypatch) -> None:
    config = JavsConfig()
    config.proxy.enabled = True
    config.proxy.url = "socks5://127.0.0.1:10808"
    config.scrapers.use_proxy["javlibrary"] = True
    captured: dict[str, object] = {}

    class DummyHttpClient:
        def __init__(self, **kwargs) -> None:
            captured["init"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get_cf(self, url: str, use_proxy: bool = False) -> str:
            captured["url"] = url
            captured["use_proxy"] = use_proxy
            return "<html>ok</html>"

    monkeypatch.setattr("javs.services.javlibrary_auth.HttpClient", DummyHttpClient)

    await validate_javlibrary_credentials(
        config,
        JavlibraryCredentials("cf-cookie", "browser-ua"),
    )

    assert captured["use_proxy"] is True
    assert captured["url"] == "https://www.javlibrary.com/en/"


def test_print_cloudflare_guidance_uses_multiline_panel(capsys) -> None:
    exc = CloudflareBlockedError(
        "Cloudflare blocked access to https://www.javlibrary.com/en/. All bypass methods failed.",
        guidance="Line 1\nLine 2",
    )

    print_cloudflare_guidance(exc)

    captured = capsys.readouterr()
    assert "Javlibrary Cloudflare" in captured.out
    assert "Line 1" in captured.out
    assert "Line 2" in captured.out
    assert str(exc) == (
        "Cloudflare blocked access to https://www.javlibrary.com/en/. "
        "All bypass methods failed."
    )
