"""Tests for reference localization."""

import csv

import pytest

from commands.comfort.localization import _BOOK_NAMES_ES, _REFERENCE_PATTERN, localize_reference


class TestLocalizeReference:
    def test_english_returns_unchanged(self) -> None:
        assert localize_reference("1 Thessalonians 4:13-14", "en") == "1 Thessalonians 4:13-14"

    def test_unmapped_language_returns_unchanged(self) -> None:
        # Only "es" has a mapping table today — anything else falls through as-is
        # rather than raising, matching framing.py's _LANGUAGE_NAMES.get(..., language)
        # fallback style elsewhere in this codebase.
        assert localize_reference("Psalm 23:4", "fr") == "Psalm 23:4"

    def test_translates_single_verse_reference(self) -> None:
        assert localize_reference("Psalm 23:4", "es") == "Salmo 23:4"

    def test_translates_verse_range_reference(self) -> None:
        assert localize_reference("1 Thessalonians 4:13-14", "es") == "1 Tesalonicenses 4:13-14"

    def test_translates_comma_separated_verse_list(self) -> None:
        assert localize_reference("James 4:6, 10", "es") == "Santiago 4:6, 10"

    def test_translates_multi_word_book_name(self) -> None:
        assert localize_reference("2 Thessalonians 1:1", "es") == "2 Tesalonicenses 1:1"

    def test_raises_on_malformed_reference(self) -> None:
        with pytest.raises(ValueError, match="doesn't match"):
            localize_reference("not a real reference", "es")

    def test_raises_on_unmapped_book(self) -> None:
        with pytest.raises(ValueError, match="No Spanish translation"):
            localize_reference("Obadiah 1:1", "es")


class TestBookCoverageAgainstRealVerseBank:
    def test_every_book_in_the_real_csv_has_a_spanish_mapping(self) -> None:
        # Regression guard: a future verse addition introducing a new book must extend
        # _BOOK_NAMES_ES, not silently fall through to an English book name mid-reply.
        books_in_csv: set[str] = set()
        with open("data/bible_OEB_verses.csv", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                match = _REFERENCE_PATTERN.match(row["reference"])
                assert match is not None, f"reference {row['reference']!r} doesn't match the expected format"
                books_in_csv.add(match.group(1))

        missing = books_in_csv - _BOOK_NAMES_ES.keys()
        assert not missing, f"Books missing from _BOOK_NAMES_ES: {sorted(missing)}"
