from lingua import Language, LanguageDetectorBuilder

from config import settings

_DETECTOR = LanguageDetectorBuilder.from_languages(
    Language.ENGLISH,
    Language.SPANISH,
).build()


def detect_language(text: str) -> str:
    """Return a BCP 47 language code for the detected language, defaulting to settings.default_language."""
    lang = _DETECTOR.detect_language_of(text)
    if lang is None:
        return settings.default_language
    return lang.iso_code_639_1.name.lower()
