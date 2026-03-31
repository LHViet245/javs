"""Translation service for movie metadata.

Replaces Javinizer's googletrans integration.
"""

from __future__ import annotations

import asyncio
import importlib.util
import inspect
import os
from dataclasses import dataclass

from javs.config.models import TranslateConfig
from javs.models.movie import MovieData
from javs.utils.logging import get_logger

logger = get_logger(__name__)


_DEEPL_TARGET_LANGUAGES = frozenset(
    {
        "AR",
        "BG",
        "CS",
        "DA",
        "DE",
        "EL",
        "EN",
        "EN-GB",
        "EN-US",
        "ES",
        "ES-419",
        "ET",
        "FI",
        "FR",
        "HE",
        "HU",
        "ID",
        "IT",
        "JA",
        "KO",
        "LT",
        "LV",
        "NB",
        "NL",
        "PL",
        "PT",
        "PT-BR",
        "PT-PT",
        "RO",
        "RU",
        "SK",
        "SL",
        "SV",
        "TH",
        "TR",
        "UK",
        "VI",
        "ZH",
        "ZH-HANS",
        "ZH-HANT",
    }
)


@dataclass(slots=True)
class TranslationProviderIssue:
    """Compact diagnostic describing why translation cannot run."""

    kind: str
    detail: str


def get_translation_provider_issue(config: TranslateConfig) -> TranslationProviderIssue | None:
    """Return a user-facing issue when the configured translation provider is unavailable."""
    if not config.enabled:
        return None

    if config.module == "googletrans":
        if importlib.util.find_spec("googletrans") is None:
            return TranslationProviderIssue(
                kind="translation_provider_unavailable",
                detail=(
                    "Install googletrans to enable translation. "
                    "Try: ./venv/bin/pip install '.[translate]'"
                ),
            )
        return None

    if config.module == "deepl":
        if importlib.util.find_spec("deepl") is None:
            return TranslationProviderIssue(
                kind="translation_provider_unavailable",
                detail=(
                    "Install deepl to enable translation. "
                    "Try: ./venv/bin/pip install '.[translate]'"
                ),
            )
        language_issue = _get_deepl_target_language_issue(config.language)
        if language_issue:
            return TranslationProviderIssue(
                kind="translation_config_invalid",
                detail=language_issue,
            )
        return None

    return TranslationProviderIssue(
        kind="translation_provider_unavailable",
        detail=f"Unknown translation module: {config.module}",
    )


async def translate_movie_data(
    data: MovieData,
    config: TranslateConfig,
) -> MovieData:
    """Translate specified fields of MovieData.

    Args:
        data: Movie metadata to translate.
        config: Translation config specifying module, language, and fields.

    Returns:
        MovieData with translated fields.
    """
    if not config.enabled:
        return data

    for field_name in config.fields:
        value = getattr(data, field_name, None)
        if not value or not isinstance(value, str):
            continue

        try:
            translated = await _translate_text(value, config)
            if translated:
                final_value = translated
                if config.keep_original_description and field_name == "description":
                    final_value = f"{translated}\n\n---\n{value}"

                setattr(data, field_name, final_value)

                if translated != value and data.field_sources.get(field_name) != config.module:
                    data.field_sources = dict(data.field_sources)
                    data.field_sources[field_name] = config.module
        except Exception as exc:
            logger.error(
                "translation_error",
                field=field_name,
                error=str(exc),
            )

    return data


async def _translate_text(text: str, config: TranslateConfig) -> str | None:
    """Translate a text string using the configured translation module.

    Args:
        text: Text to translate.
        config: Translation config.

    Returns:
        Translated text or None on failure.
    """
    if config.module == "googletrans":
        return await _translate_googletrans(text, config.language)
    elif config.module == "deepl":
        return await _translate_deepl(text, config.language, _get_effective_deepl_api_key(config))
    else:
        logger.warning("unknown_translate_module", module=config.module)
        return None


async def _translate_googletrans(text: str, dest_lang: str) -> str | None:
    """Translate using googletrans."""
    try:
        from googletrans import Translator

        async def _async_translate() -> str:
            translator = Translator()
            if hasattr(translator, "__aenter__") and hasattr(translator, "__aexit__"):
                async with translator as active_translator:
                    result = active_translator.translate(text, dest=dest_lang)
                    if inspect.isawaitable(result):
                        result = await result
                    return result.text

            result = translator.translate(text, dest=dest_lang)
            if inspect.isawaitable(result):
                result = await result
            return result.text

        return await _async_translate()
    except ImportError:
        logger.error("googletrans_not_installed", msg="pip install googletrans>=4.0.2")
        return None
    except Exception as exc:
        logger.error("googletrans_error", error=str(exc))
        return None


async def _translate_deepl(text: str, target_lang: str, api_key: str) -> str | None:
    """Translate using DeepL API."""
    language_issue = _get_deepl_target_language_issue(target_lang)
    if language_issue:
        logger.error("deepl_invalid_target_lang", error=language_issue)
        return None

    try:
        import deepl

        def _sync_translate() -> str:
            translator = deepl.Translator(api_key)
            result = translator.translate_text(
                text,
                target_lang=_normalize_deepl_target_language(target_lang),
            )
            return result.text

        return await asyncio.to_thread(_sync_translate)
    except ImportError:
        logger.error("deepl_not_installed", msg="pip install deepl")
        return None
    except Exception as exc:
        logger.error("deepl_error", error=str(exc))
        return None


def _normalize_deepl_target_language(target_lang: str) -> str:
    """Normalize DeepL target language casing and separators."""
    return target_lang.strip().replace("_", "-").upper()


def _get_effective_deepl_api_key(config: TranslateConfig) -> str:
    """Prefer runtime env override without persisting it into config files."""
    return os.getenv("DEEPL_API_KEY") or config.deepl_api_key


def _get_deepl_target_language_issue(target_lang: str) -> str | None:
    """Return a user-facing validation message for invalid DeepL target languages."""
    normalized = _normalize_deepl_target_language(target_lang)
    if not normalized:
        return "DeepL language cannot be empty."
    if normalized not in _DEEPL_TARGET_LANGUAGES:
        return (
            f"DeepL language '{target_lang}' is not a supported target language. "
            "Use a supported DeepL target code such as 'en-us', 'ja', 'vi', or 'pt-br'."
        )
    return None
