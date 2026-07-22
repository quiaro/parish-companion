import pytest

import config
from translations import STRINGS, get_string

_SUPPORTED_LANGUAGES = ["en", "es"]
_ALL_KEYS = list(STRINGS["en"].keys())


def test_all_languages_have_all_keys() -> None:
    """Every language in the catalogue must define every key present in 'en'."""
    for lang in _SUPPORTED_LANGUAGES:
        for key in _ALL_KEYS:
            assert key in STRINGS[lang], f"Missing key '{key}' in language '{lang}'"


def test_get_string_returns_empty_string_and_logs_error_when_key_missing(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    import logging
    monkeypatch.setattr(config.settings, "default_language", "en")
    with caplog.at_level(logging.ERROR, logger="translations"):
        result = get_string("nonexistent_key", "en")
    assert result == ""
    assert any("nonexistent_key" in m for m in caplog.messages)


# Keys where the correct Spanish word genuinely happens to be spelled the same as
# English (a real linguistic coincidence, not a forgotten translation).
_EXPECTED_IDENTICAL_KEYS = {"comfort_button_no"}


def test_en_and_es_strings_are_different() -> None:
    """Sanity check: translations are not identical to the English source."""
    for key in _ALL_KEYS:
        if key in _EXPECTED_IDENTICAL_KEYS:
            continue
        assert STRINGS["en"][key] != STRINGS["es"][key], (
            f"English and Spanish strings are identical for key '{key}'"
        )
