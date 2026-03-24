"""Translation service for movie metadata.

Replaces Javinizer's googletrans integration.
"""

from __future__ import annotations

import asyncio
import importlib.util
from dataclasses import dataclass

from javs.config.models import TranslateConfig
from javs.models.movie import MovieData
from javs.utils.logging import get_logger

logger = get_logger(__name__)


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
                if config.keep_original_description and field_name == "description":
                    setattr(data, field_name, f"{translated}\n\n---\n{value}")
                else:
                    setattr(data, field_name, translated)
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
        return await _translate_deepl(text, config.language, config.deepl_api_key)
    else:
        logger.warning("unknown_translate_module", module=config.module)
        return None


async def _translate_googletrans(text: str, dest_lang: str) -> str | None:
    """Translate using googletrans."""
    try:
        from googletrans import Translator

        def _sync_translate() -> str:
            translator = Translator()
            result = translator.translate(text, dest=dest_lang)
            return result.text

        return await asyncio.to_thread(_sync_translate)
    except ImportError:
        logger.error("googletrans_not_installed", msg="pip install googletrans==4.0.0-rc.1")
        return None
    except Exception as exc:
        logger.error("googletrans_error", error=str(exc))
        return None


async def _translate_deepl(text: str, target_lang: str, api_key: str) -> str | None:
    """Translate using DeepL API."""
    try:
        import deepl

        def _sync_translate() -> str:
            translator = deepl.Translator(api_key)
            result = translator.translate_text(text, target_lang=target_lang.upper())
            return result.text

        return await asyncio.to_thread(_sync_translate)
    except ImportError:
        logger.error("deepl_not_installed", msg="pip install deepl")
        return None
    except Exception as exc:
        logger.error("deepl_error", error=str(exc))
        return None
