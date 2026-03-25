"""Tests for the translation service."""

from __future__ import annotations

import builtins
from types import ModuleType, SimpleNamespace

import pytest

from javs.config.models import TranslateConfig
from javs.models.movie import MovieData
from javs.services import translator as translator_module


def _movie_data() -> MovieData:
    return MovieData(
        id="ABP-420",
        title="Original title",
        description="Original description",
        maker="Studio",
    )


class TestTranslateMovieData:
    """Test the public translation entrypoint."""

    @pytest.mark.asyncio
    async def test_disabled_config_returns_original_object(self) -> None:
        data = _movie_data()
        config = TranslateConfig(enabled=False)

        result = await translator_module.translate_movie_data(data, config)

        assert result is data
        assert result.title == "Original title"
        assert result.description == "Original description"

    @pytest.mark.asyncio
    async def test_skips_missing_and_non_string_fields(self, monkeypatch) -> None:
        data = MovieData(
            id="ABP-420",
            title="Translate me",
            description=None,
            runtime=120,
        )
        config = TranslateConfig(
            enabled=True,
            fields=["title", "description", "runtime", "missing_field"],
        )
        calls: list[str] = []

        async def fake_translate_text(text: str, cfg: TranslateConfig) -> str | None:
            calls.append(text)
            return f"translated:{text}"

        monkeypatch.setattr(translator_module, "_translate_text", fake_translate_text)

        result = await translator_module.translate_movie_data(data, config)

        assert result.title == "translated:Translate me"
        assert result.description is None
        assert result.runtime == 120
        assert calls == ["Translate me"]

    @pytest.mark.asyncio
    async def test_translates_title_and_preserves_original_description(
        self, monkeypatch
    ) -> None:
        data = _movie_data()
        config = TranslateConfig(
            enabled=True,
            fields=["title", "description"],
            keep_original_description=True,
        )

        async def fake_translate_text(text: str, cfg: TranslateConfig) -> str | None:
            del cfg
            return f"translated:{text}"

        monkeypatch.setattr(translator_module, "_translate_text", fake_translate_text)

        result = await translator_module.translate_movie_data(data, config)

        assert result.title == "translated:Original title"
        assert result.description == (
            "translated:Original description\n\n---\nOriginal description"
        )

    @pytest.mark.asyncio
    async def test_changed_translation_overrides_field_source(self, monkeypatch) -> None:
        data = MovieData(
            id="ABP-420",
            description="Original description",
            title="Original title",
            field_sources={"description": "dmm", "title": "r18dev"},
        )
        config = TranslateConfig(enabled=True, module="deepl", fields=["description"])

        async def fake_translate_text(text: str, cfg: TranslateConfig) -> str | None:
            del text, cfg
            return "Translated description"

        monkeypatch.setattr(translator_module, "_translate_text", fake_translate_text)

        result = await translator_module.translate_movie_data(data, config)

        assert result.description == "Translated description"
        assert result.field_sources["description"] == "deepl"
        assert result.field_sources["title"] == "r18dev"

    @pytest.mark.asyncio
    async def test_unchanged_translation_preserves_field_source(self, monkeypatch) -> None:
        data = MovieData(
            id="ABP-420",
            description="Original description",
            field_sources={"description": "dmm"},
        )
        original_field_sources = data.field_sources
        config = TranslateConfig(enabled=True, module="deepl", fields=["description"])

        async def fake_translate_text(text: str, cfg: TranslateConfig) -> str | None:
            del cfg
            return text

        monkeypatch.setattr(translator_module, "_translate_text", fake_translate_text)

        result = await translator_module.translate_movie_data(data, config)

        assert result.description == "Original description"
        assert result.field_sources["description"] == "dmm"
        assert result.field_sources is original_field_sources

    @pytest.mark.asyncio
    async def test_unchanged_translation_with_original_description_preserves_provenance(
        self, monkeypatch
    ) -> None:
        data = MovieData(
            id="ABP-420",
            description="Original description",
            field_sources={"description": "dmm"},
        )
        original_field_sources = data.field_sources
        config = TranslateConfig(
            enabled=True,
            module="deepl",
            fields=["description"],
            keep_original_description=True,
        )

        async def fake_translate_text(text: str, cfg: TranslateConfig) -> str | None:
            del cfg
            return text

        monkeypatch.setattr(translator_module, "_translate_text", fake_translate_text)

        result = await translator_module.translate_movie_data(data, config)

        assert result.description == (
            "Original description\n\n---\nOriginal description"
        )
        assert result.field_sources["description"] == "dmm"
        assert result.field_sources is original_field_sources

    @pytest.mark.asyncio
    async def test_none_translation_preserves_field_source(self, monkeypatch) -> None:
        data = MovieData(
            id="ABP-420",
            description="Original description",
            field_sources={"description": "dmm"},
        )
        original_field_sources = data.field_sources
        config = TranslateConfig(enabled=True, module="deepl", fields=["description"])

        async def fake_translate_text(text: str, cfg: TranslateConfig) -> str | None:
            del text, cfg
            return None

        monkeypatch.setattr(translator_module, "_translate_text", fake_translate_text)

        result = await translator_module.translate_movie_data(data, config)

        assert result.description == "Original description"
        assert result.field_sources["description"] == "dmm"
        assert result.field_sources is original_field_sources


class TestTranslateText:
    """Test module selection and fallback behavior."""

    def test_get_translation_provider_issue_accepts_generic_deepl_english_target(
        self,
        monkeypatch,
    ) -> None:
        config = TranslateConfig(enabled=True, module="deepl", language="en")

        monkeypatch.setattr(
            translator_module.importlib.util,
            "find_spec",
            lambda name: object() if name == "deepl" else None,
        )

        issue = translator_module.get_translation_provider_issue(config)

        assert issue is None

    def test_get_translation_provider_issue_accepts_valid_deepl_variant(
        self,
        monkeypatch,
    ) -> None:
        config = TranslateConfig(enabled=True, module="deepl", language="en-us")

        monkeypatch.setattr(
            translator_module.importlib.util,
            "find_spec",
            lambda name: object() if name == "deepl" else None,
        )

        issue = translator_module.get_translation_provider_issue(config)

        assert issue is None

    def test_get_effective_deepl_api_key_prefers_environment(self, monkeypatch) -> None:
        config = TranslateConfig(enabled=True, module="deepl", deepl_api_key="from-file")
        monkeypatch.setenv("DEEPL_API_KEY", "from-env")

        assert translator_module._get_effective_deepl_api_key(config) == "from-env"

    def test_get_effective_deepl_api_key_falls_back_to_config(self, monkeypatch) -> None:
        config = TranslateConfig(enabled=True, module="deepl", deepl_api_key="from-file")
        monkeypatch.delenv("DEEPL_API_KEY", raising=False)

        assert translator_module._get_effective_deepl_api_key(config) == "from-file"

    def test_get_translation_provider_issue_returns_install_hint_for_missing_googletrans(
        self,
        monkeypatch,
    ) -> None:
        config = TranslateConfig(enabled=True, module="googletrans", language="en")

        monkeypatch.setattr(
            translator_module.importlib.util,
            "find_spec",
            lambda name: None if name == "googletrans" else object(),
        )

        issue = translator_module.get_translation_provider_issue(config)

        assert issue is not None
        assert issue.kind == "translation_provider_unavailable"
        assert "googletrans" in issue.detail

    def test_get_translation_provider_issue_returns_none_when_provider_is_available(
        self,
        monkeypatch,
    ) -> None:
        config = TranslateConfig(enabled=True, module="deepl", language="en-us")

        monkeypatch.setattr(
            translator_module.importlib.util,
            "find_spec",
            lambda name: object() if name == "deepl" else None,
        )

        issue = translator_module.get_translation_provider_issue(config)

        assert issue is None

    @pytest.mark.asyncio
    async def test_unknown_module_returns_none(self) -> None:
        config = TranslateConfig(enabled=True, module="unknown", language="en")

        result = await translator_module._translate_text("hello", config)

        assert result is None

    @pytest.mark.asyncio
    async def test_googletrans_success(self, monkeypatch) -> None:
        class FakeTranslated:
            text = "translated hello"

        class FakeTranslator:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def translate(self, text: str, dest: str) -> FakeTranslated:
                assert text == "hello"
                assert dest == "ja"
                return FakeTranslated()

        fake_module = ModuleType("googletrans")
        fake_module.Translator = FakeTranslator
        monkeypatch.setitem(__import__("sys").modules, "googletrans", fake_module)

        result = await translator_module._translate_googletrans("hello", "ja")

        assert result == "translated hello"

    @pytest.mark.asyncio
    async def test_googletrans_importerror_returns_none(self, monkeypatch) -> None:
        real_import = builtins.__import__

        def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "googletrans":
                raise ImportError("blocked for test")
            return real_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", blocked_import)

        result = await translator_module._translate_googletrans("hello", "ja")

        assert result is None

    @pytest.mark.asyncio
    async def test_googletrans_exception_returns_none(self, monkeypatch) -> None:
        class FakeTranslator:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def translate(self, text: str, dest: str) -> SimpleNamespace:
                del text, dest
                raise RuntimeError("boom")

        fake_module = ModuleType("googletrans")
        fake_module.Translator = FakeTranslator
        monkeypatch.setitem(__import__("sys").modules, "googletrans", fake_module)

        result = await translator_module._translate_googletrans("hello", "ja")

        assert result is None

    @pytest.mark.asyncio
    async def test_deepl_success(self, monkeypatch) -> None:
        class FakeTranslated:
            text = "translated hello"

        class FakeTranslator:
            def __init__(self, api_key: str) -> None:
                assert api_key == "secret-key"

            def translate_text(self, text: str, target_lang: str) -> FakeTranslated:
                assert text == "hello"
                assert target_lang == "JA"
                return FakeTranslated()

        fake_module = ModuleType("deepl")
        fake_module.Translator = FakeTranslator
        monkeypatch.setitem(__import__("sys").modules, "deepl", fake_module)

        async def fake_to_thread(func):
            return func()

        monkeypatch.setattr(translator_module.asyncio, "to_thread", fake_to_thread)

        result = await translator_module._translate_deepl("hello", "ja", "secret-key")

        assert result == "translated hello"

    @pytest.mark.asyncio
    async def test_deepl_success_normalizes_language_variant(self, monkeypatch) -> None:
        class FakeTranslated:
            text = "translated hello"

        class FakeTranslator:
            def __init__(self, api_key: str) -> None:
                assert api_key == "secret-key"

            def translate_text(self, text: str, target_lang: str) -> FakeTranslated:
                assert text == "hello"
                assert target_lang == "EN-US"
                return FakeTranslated()

        fake_module = ModuleType("deepl")
        fake_module.Translator = FakeTranslator
        monkeypatch.setitem(__import__("sys").modules, "deepl", fake_module)

        async def fake_to_thread(func):
            return func()

        monkeypatch.setattr(translator_module.asyncio, "to_thread", fake_to_thread)

        result = await translator_module._translate_deepl("hello", "en-us", "secret-key")

        assert result == "translated hello"

    @pytest.mark.asyncio
    async def test_deepl_generic_english_target_is_allowed(self, monkeypatch) -> None:
        class FakeTranslated:
            text = "translated hello"

        class FakeTranslator:
            def __init__(self, api_key: str) -> None:
                assert api_key == "secret-key"

            def translate_text(self, text: str, target_lang: str) -> FakeTranslated:
                assert text == "hello"
                assert target_lang == "EN"
                return FakeTranslated()

        fake_module = ModuleType("deepl")
        fake_module.Translator = FakeTranslator
        monkeypatch.setitem(__import__("sys").modules, "deepl", fake_module)

        async def fake_to_thread(func):
            return func()

        monkeypatch.setattr(translator_module.asyncio, "to_thread", fake_to_thread)

        result = await translator_module._translate_deepl("hello", "en", "secret-key")

        assert result == "translated hello"

    @pytest.mark.asyncio
    async def test_deepl_importerror_returns_none(self, monkeypatch) -> None:
        real_import = builtins.__import__

        def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "deepl":
                raise ImportError("blocked for test")
            return real_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", blocked_import)

        result = await translator_module._translate_deepl("hello", "ja", "secret-key")

        assert result is None

    @pytest.mark.asyncio
    async def test_deepl_exception_returns_none(self, monkeypatch) -> None:
        class FakeTranslator:
            def __init__(self, api_key: str) -> None:
                del api_key

            def translate_text(self, text: str, target_lang: str) -> SimpleNamespace:
                del text, target_lang
                raise RuntimeError("boom")

        fake_module = ModuleType("deepl")
        fake_module.Translator = FakeTranslator
        monkeypatch.setitem(__import__("sys").modules, "deepl", fake_module)

        async def fake_to_thread(func):
            return func()

        monkeypatch.setattr(translator_module.asyncio, "to_thread", fake_to_thread)

        result = await translator_module._translate_deepl("hello", "ja", "secret-key")

        assert result is None
