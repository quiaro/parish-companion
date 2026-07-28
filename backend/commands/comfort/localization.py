"""
Verse-content localization

Verse references are stored (and used as Qdrant point IDs) in English i.e. they're 
language-agnostic internally. Only the book name needs translating for display so
only the book name is mechanically extracted and substituted; chapter/verse numbers 
are identical across languages.
"""

import re

# Standard Spanish book names — consistent across mainstream Spanish Bible translations
# (Reina-Valera, Biblia de Jerusalén, NVI, etc.), so unlike verse wording itself, this is
# a fixed reference table rather than something requiring per-verse curation.
_BOOK_NAMES_ES = {
    "1 Corinthians": "1 Corintios",
    "1 John": "1 Juan",
    "1 Peter": "1 Pedro",
    "1 Thessalonians": "1 Tesalonicenses",
    "2 Corinthians": "2 Corintios",
    "2 Peter": "2 Pedro",
    "2 Thessalonians": "2 Tesalonicenses",
    "2 Timothy": "2 Timoteo",
    "Acts": "Hechos",
    "Colossians": "Colosenses",
    "Ephesians": "Efesios",
    "Galatians": "Gálatas",
    "Genesis": "Génesis",
    "Habakkuk": "Habacuc",
    "Hebrews": "Hebreos",
    "James": "Santiago",
    "Joel": "Joel",
    "John": "Juan",
    "Jonah": "Jonás",
    "Joshua": "Josué",
    "Jude": "Judas",
    "Luke": "Lucas",
    "Mark": "Marcos",
    "Matthew": "Mateo",
    "Micah": "Miqueas",
    "Nahum": "Nahúm",
    "Philippians": "Filipenses",
    "Psalm": "Salmo",
    "Revelation": "Apocalipsis",
    "Romans": "Romanos",
    "Titus": "Tito",
    "Zephaniah": "Sofonías",
}

# Matches "<book name> <chapter>:<verse>", where the verse part may be a range
# ("4:13-14") and/or a comma-separated list of verses/ranges ("4:6, 10", "1:1-3, 8").
_REFERENCE_PATTERN = re.compile(r"^(.+?)\s+(\d+:\d+(?:-\d+)?(?:,\s*\d+(?:-\d+)?)*)$")


def localize_reference(reference: str, language: str) -> str:
    """Returns the reference unchanged for English (or any language without a mapping
    table). For Spanish, splits off the book name and substitutes its Spanish form,
    raising if the book isn't in the mapping —a curation gap that should be fixed by
    extending _BOOK_NAMES_ES."""
    if language != "es":
        return reference

    match = _REFERENCE_PATTERN.match(reference)
    if match is None:
        raise ValueError(f"Reference {reference!r} doesn't match the expected '<book> <chapter>:<verse>' format")

    book, chapter_verse = match.groups()
    localized_book = _BOOK_NAMES_ES.get(book)
    if localized_book is None:
        raise ValueError(f"No Spanish translation for book {book!r} — add it to _BOOK_NAMES_ES")

    return f"{localized_book} {chapter_verse}"
