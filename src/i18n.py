"""Internationalization (i18n) support for Web UI."""
from __future__ import annotations

import json
from pathlib import Path

_LOCALES_DIR = Path(__file__).parent / "locales"
_DEFAULT_LANG = "en"
_SUPPORTED_LANGS: set[str] = set()
_MESSAGES: dict[str, dict[str, str]] = {}


def _load_messages() -> None:
    """Load all locale JSON files."""
    for path in _LOCALES_DIR.glob("*.json"):
        lang = path.stem
        with open(path, encoding="utf-8") as f:
            _MESSAGES[lang] = json.load(f)
        _SUPPORTED_LANGS.add(lang)


_load_messages()


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


def get_translator(lang: str):
    """Return a translation function for the given language."""
    messages = _MESSAGES.get(lang, _MESSAGES.get(_DEFAULT_LANG, {}))
    fallback = _MESSAGES.get(_DEFAULT_LANG, {})

    def t(key: str) -> str:
        return messages.get(key, fallback.get(key, key))

    return t
