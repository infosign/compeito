"""Internationalization (i18n) support for Web UI and CLI."""

from __future__ import annotations

import json
import os
from pathlib import Path

_LOCALES_DIR = Path(__file__).parent / "locales"
_DEFAULT_LANG = "en"
_SUPPORTED_LANGS: set[str] = set()
_MESSAGES: dict[str, dict[str, str]] = {}
_CLI_MESSAGES: dict[str, dict[str, str]] = {}


def _load_messages() -> None:
    """Load all locale JSON files (web and CLI)."""
    for path in _LOCALES_DIR.glob("*.json"):
        name = path.stem
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if name.startswith("cli_"):
            lang = name[4:]  # "cli_ja" -> "ja"
            _CLI_MESSAGES[lang] = data
        else:
            lang = name
            _MESSAGES[lang] = data
        _SUPPORTED_LANGS.add(lang)


_load_messages()


def detect_lang_from_env() -> str:
    """Detect language from LANG environment variable.

    Example: "ja_JP.UTF-8" -> "ja", "en_US.UTF-8" -> "en"
    """
    lang_env = os.environ.get("LANG", "")
    if lang_env:
        lang = lang_env.split("_")[0].split(".")[0].lower()
        if lang in _SUPPORTED_LANGS:
            return lang
    return _DEFAULT_LANG


def parse_accept_language(header: str) -> str:
    """Parse Accept-Language header and return best matching language.

    Example: "ja,en-US;q=0.9,en;q=0.8" -> "ja"
    """
    if not header:
        return _DEFAULT_LANG

    # Parse language tags with quality values
    langs: list[tuple[str, float]] = []
    for part in header.split(","):
        part = part.strip()
        if ";q=" in part:
            tag, q = part.split(";q=", 1)
            try:
                quality = float(q.strip())
            except ValueError:
                quality = 0.0
        else:
            tag = part
            quality = 1.0
        # Normalize: "en-US" -> "en"
        lang = tag.strip().split("-")[0].lower()
        langs.append((lang, quality))

    # Sort by quality descending
    langs.sort(key=lambda x: x[1], reverse=True)

    for lang, _ in langs:
        if lang in _SUPPORTED_LANGS:
            return lang

    return _DEFAULT_LANG


def get_translator(lang: str, *, cli: bool = False):
    """Return a translation function for the given language.

    Args:
        lang: Language code (e.g. "en", "ja")
        cli: If True, use CLI message catalog instead of web catalog
    """
    catalog = _CLI_MESSAGES if cli else _MESSAGES
    messages = catalog.get(lang, catalog.get(_DEFAULT_LANG, {}))
    fallback = catalog.get(_DEFAULT_LANG, {})

    def t(key: str, **kwargs: str) -> str:
        msg = messages.get(key, fallback.get(key, key))
        if kwargs:
            for k, v in kwargs.items():
                msg = msg.replace(f"{{{k}}}", v)
        return msg

    return t
