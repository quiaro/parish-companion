"""Tests for the Bible verse-bank ingestion script's pure logic — no real OpenRouter
or Qdrant calls, since this is a one-off/occasional operational script, not
request-handling code."""

import csv
import json

import pytest

from scripts.ingest_verses import VerseRow, _point_id, _synthesize_embedding_text, load_verses

_ROW = VerseRow(
    reference="Psalm 23:4",
    verse_text="And when my way lies through a valley of gloom...",
    emotional_tags=["fear", "grief"],
    situational_tags=["bereavement", "terminal_illness"],
    example_user_phrasings=["I'm scared.", "I feel alone."],
)


class TestSynthesizeEmbeddingText:
    def test_includes_emotional_tags(self) -> None:
        text = _synthesize_embedding_text(_ROW)
        assert "fear, grief" in text

    def test_includes_situational_tags(self) -> None:
        text = _synthesize_embedding_text(_ROW)
        assert "bereavement, terminal_illness" in text

    def test_includes_example_phrasings(self) -> None:
        text = _synthesize_embedding_text(_ROW)
        assert "I'm scared." in text
        assert "I feel alone." in text

    def test_does_not_include_raw_verse_text(self) -> None:
        # The whole point is embedding the tags/phrasings, not the verse itself.
        text = _synthesize_embedding_text(_ROW)
        assert _ROW.verse_text not in text

    def test_omits_situational_tags_section_when_empty(self) -> None:
        row = VerseRow(
            reference="Romans 5:3-5",
            verse_text="...",
            emotional_tags=["hope"],
            situational_tags=[],
            example_user_phrasings=["I want to believe this will make me stronger."],
        )
        text = _synthesize_embedding_text(row)
        assert "Situational tags" not in text
        assert "hope" in text


class TestPointId:
    def test_deterministic_for_same_reference(self) -> None:
        assert _point_id("Psalm 23:4") == _point_id("Psalm 23:4")

    def test_different_for_different_references(self) -> None:
        assert _point_id("Psalm 23:4") != _point_id("Romans 5:3-5")


class TestLoadVerses:
    def test_loads_the_real_verse_csv(self) -> None:
        # Row count is derived from the file itself, not hardcoded — the CSV is
        # expected to grow/shrink as verses are curated, and this should only fail
        # if load_verses actually drops or duplicates rows, not whenever content changes.
        with open("data/bible_OEB_verses.csv", encoding="utf-8") as f:
            expected_count = sum(1 for _ in f) - 1  # minus the header row
        rows = load_verses("data/bible_OEB_verses.csv")
        assert len(rows) == expected_count
        assert len(rows) > 0

    def test_parses_fields_correctly(self) -> None:
        rows = load_verses("data/bible_OEB_verses.csv")
        first = next(r for r in rows if r.reference == "Psalm 23:4")
        assert "valley of gloom" in first.verse_text
        assert "fear" in first.emotional_tags
        assert "bereavement" in first.situational_tags
        assert len(first.example_user_phrasings) == 3

    def test_raises_on_unrecognized_emotional_tag(self, tmp_path) -> None:
        csv_path = tmp_path / "bad.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["verse", "reference", "emotional_tags", "situational_tags", "example_user_phrasings"])
            writer.writerow(["Test verse", "Test 1:1", json.dumps(["not_a_real_tag"]), "[]", "[]"])

        with pytest.raises(ValueError, match="not_a_real_tag"):
            load_verses(str(csv_path))

    def test_raises_on_unrecognized_situational_tag(self, tmp_path) -> None:
        csv_path = tmp_path / "bad.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["verse", "reference", "emotional_tags", "situational_tags", "example_user_phrasings"])
            writer.writerow(["Test verse", "Test 1:1", "[]", json.dumps(["not_a_real_situation"]), "[]"])

        with pytest.raises(ValueError, match="not_a_real_situation"):
            load_verses(str(csv_path))

    def test_reports_all_problems_not_just_the_first(self, tmp_path) -> None:
        csv_path = tmp_path / "bad.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["verse", "reference", "emotional_tags", "situational_tags", "example_user_phrasings"])
            writer.writerow(["Verse one", "Test 1:1", json.dumps(["bad_one"]), "[]", "[]"])
            writer.writerow(["Verse two", "Test 1:2", json.dumps(["bad_two"]), "[]", "[]"])

        with pytest.raises(ValueError) as exc_info:
            load_verses(str(csv_path))
        assert "bad_one" in str(exc_info.value)
        assert "bad_two" in str(exc_info.value)
