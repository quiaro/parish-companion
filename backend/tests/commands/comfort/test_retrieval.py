"""Tests for K-07 Step F/G retrieval logic — Qdrant and the embedding call are mocked."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import config
from commands.comfort import retrieval
from commands.comfort.models import ClassificationResult, EmotionalTag
from db.parishioners import SentPassage

_UID = 12345


def _point(
    reference: str,
    score: float,
    emotional_tags=None,
    situational_tags=None,
    verse_text="verse text",
    verse_text_es="texto del verso",
):
    return SimpleNamespace(
        score=score,
        payload={
            "reference": reference,
            "verse_text": verse_text,
            "verse_text_es": verse_text_es,
            "emotional_tags": emotional_tags or [],
            "situational_tags": situational_tags or [],
        },
    )


@pytest.fixture(autouse=True)
def similarity_threshold(monkeypatch):
    monkeypatch.setattr(config.settings, "comfort_similarity_threshold", 0.75)


@pytest.fixture(autouse=True)
def embed_mock(monkeypatch):
    mock = AsyncMock(return_value=[0.1, 0.2, 0.3])
    monkeypatch.setattr(retrieval, "_embed", mock)
    return mock


@pytest.fixture
def recent_passages_mock(monkeypatch):
    mock = MagicMock(return_value=[])
    monkeypatch.setattr(retrieval, "get_recent_sent_passages", mock)
    return mock


@pytest.fixture
def query_points_mock(monkeypatch):
    mock = AsyncMock()
    monkeypatch.setattr(retrieval.qdrant, "query_points", mock)
    return mock


@pytest.fixture
def scroll_mock(monkeypatch):
    mock = AsyncMock(return_value=([], None))
    monkeypatch.setattr(retrieval.qdrant, "scroll", mock)
    return mock


@pytest.fixture
def fixed_random_choice(monkeypatch):
    def choose_first(seq):
        return seq[0]

    monkeypatch.setattr(retrieval.random, "choice", choose_first)


_NO_TAGS_RESULT = ClassificationResult(is_crisis=False)


class TestTopMatch:
    @pytest.mark.asyncio
    async def test_top_candidate_above_threshold_and_new_is_selected(
        self, recent_passages_mock, query_points_mock
    ) -> None:
        query_points_mock.return_value = SimpleNamespace(
            points=[_point("Psalm 23:4", 0.9), _point("Romans 5:3-5", 0.8)]
        )
        passage = await retrieval.retrieve_passage(_UID, "I'm scared", _NO_TAGS_RESULT)

        assert passage.reference == "Psalm 23:4"
        assert passage.is_fallback is False
        query_points_mock.assert_awaited_once_with(
            collection_name=config.settings.qdrant_collection_name, query=[0.1, 0.2, 0.3], limit=40, with_payload=True
        )

    @pytest.mark.asyncio
    async def test_embeds_the_raw_text_directly(self, recent_passages_mock, query_points_mock, embed_mock) -> None:
        query_points_mock.return_value = SimpleNamespace(points=[_point("Psalm 23:4", 0.9)])
        await retrieval.retrieve_passage(_UID, "I'm scared", _NO_TAGS_RESULT)
        embed_mock.assert_awaited_once_with("I'm scared")


class TestRecencyExclusion:
    @pytest.mark.asyncio
    async def test_recently_sent_candidate_is_skipped_for_the_next_one(
        self, recent_passages_mock, query_points_mock
    ) -> None:
        recent_passages_mock.return_value = [SentPassage(passage_reference="Psalm 23:4", sent_at=datetime.now())]
        query_points_mock.return_value = SimpleNamespace(
            points=[_point("Psalm 23:4", 0.9), _point("Romans 5:3-5", 0.8)]
        )
        passage = await retrieval.retrieve_passage(_UID, "I'm scared", _NO_TAGS_RESULT)

        assert passage.reference == "Romans 5:3-5"
        assert passage.is_fallback is False


class TestBelowThreshold:
    @pytest.mark.asyncio
    async def test_below_threshold_candidate_falls_back(
        self, recent_passages_mock, query_points_mock, scroll_mock, fixed_random_choice
    ) -> None:
        # Psalm 23:4 is above threshold but already sent recently, so it's skipped; the
        # next candidate is below threshold, which should end the search immediately.
        recent_passages_mock.return_value = [SentPassage(passage_reference="Psalm 23:4", sent_at=datetime.now())]
        query_points_mock.return_value = SimpleNamespace(
            points=[_point("Psalm 23:4", 0.9), _point("Romans 5:3-5", 0.7)]
        )
        scroll_mock.return_value = ([_point("Philippians 4:13", 1.0)], None)

        passage = await retrieval.retrieve_passage(_UID, "I'm scared", _NO_TAGS_RESULT)

        assert passage.is_fallback is True
        query_points_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_first_candidate_below_threshold_falls_back(
        self, recent_passages_mock, query_points_mock, scroll_mock, fixed_random_choice
    ) -> None:
        query_points_mock.return_value = SimpleNamespace(points=[_point("Psalm 23:4", 0.5)])
        scroll_mock.return_value = ([_point("Philippians 4:13", 1.0)], None)

        passage = await retrieval.retrieve_passage(_UID, "I'm scared", _NO_TAGS_RESULT)

        assert passage.reference == "Philippians 4:13"
        assert passage.is_fallback is True


class TestSingleQuery:
    @pytest.mark.asyncio
    async def test_finds_a_match_further_down_the_single_batch(
        self, recent_passages_mock, query_points_mock
    ) -> None:
        # All of the first 10 (above threshold) are recently sent; a later candidate in
        # the same up-to-40 batch, still above threshold, is new and gets selected — all
        # from a single query_points call.
        recent_passages_mock.return_value = [SentPassage(passage_reference=f"R{i}", sent_at=datetime.now()) for i in range(10)]
        points = [_point(f"R{i}", 0.9 - i * 0.01) for i in range(10)] + [_point("New Verse 1:1", 0.79)]
        query_points_mock.return_value = SimpleNamespace(points=points)

        passage = await retrieval.retrieve_passage(_UID, "I'm scared", _NO_TAGS_RESULT)

        assert passage.reference == "New Verse 1:1"
        assert passage.is_fallback is False
        query_points_mock.assert_awaited_once_with(
            collection_name=config.settings.qdrant_collection_name, query=[0.1, 0.2, 0.3], limit=40, with_payload=True
        )

    @pytest.mark.asyncio
    async def test_falls_back_when_all_40_results_are_recently_sent(
        self, recent_passages_mock, query_points_mock, scroll_mock, fixed_random_choice
    ) -> None:
        recent_passages_mock.return_value = [SentPassage(passage_reference=f"R{i}", sent_at=datetime.now()) for i in range(40)]
        query_points_mock.return_value = SimpleNamespace(
            points=[_point(f"R{i}", 0.9 - i * 0.001) for i in range(40)]
        )
        scroll_mock.return_value = ([_point("Philippians 4:13", 1.0)], None)

        passage = await retrieval.retrieve_passage(_UID, "I'm scared", _NO_TAGS_RESULT)

        assert passage.is_fallback is True
        query_points_mock.assert_awaited_once()


class TestTagMismatchLogging:
    @pytest.mark.asyncio
    async def test_logs_warning_when_no_shared_tags(
        self, recent_passages_mock, query_points_mock, caplog
    ) -> None:
        query_points_mock.return_value = SimpleNamespace(
            points=[_point("Psalm 23:4", 0.9, emotional_tags=["joy"])]
        )
        result = ClassificationResult(is_crisis=False, emotional_tags=[EmotionalTag.GRIEF])
        with caplog.at_level("WARNING"):
            await retrieval.retrieve_passage(_UID, "I'm grieving", result)
        assert any("shares no tags" in message for message in caplog.messages)

    @pytest.mark.asyncio
    async def test_no_warning_when_tags_overlap(self, recent_passages_mock, query_points_mock, caplog) -> None:
        query_points_mock.return_value = SimpleNamespace(
            points=[_point("Psalm 23:4", 0.9, emotional_tags=["grief"])]
        )
        result = ClassificationResult(is_crisis=False, emotional_tags=[EmotionalTag.GRIEF])
        with caplog.at_level("WARNING"):
            await retrieval.retrieve_passage(_UID, "I'm grieving", result)
        assert not any("shares no tags" in message for message in caplog.messages)

    @pytest.mark.asyncio
    async def test_no_warning_when_classification_has_no_tags(
        self, recent_passages_mock, query_points_mock, caplog
    ) -> None:
        query_points_mock.return_value = SimpleNamespace(
            points=[_point("Psalm 23:4", 0.9, emotional_tags=["joy"])]
        )
        with caplog.at_level("WARNING"):
            await retrieval.retrieve_passage(_UID, "hello", _NO_TAGS_RESULT)
        assert not any("shares no tags" in message for message in caplog.messages)


class TestFallbackPassage:
    @pytest.mark.asyncio
    async def test_fallback_filters_on_faith_hope_love(
        self, recent_passages_mock, query_points_mock, scroll_mock, fixed_random_choice
    ) -> None:
        query_points_mock.return_value = SimpleNamespace(points=[_point("Psalm 23:4", 0.1)])
        scroll_mock.return_value = ([_point("Philippians 4:13", 1.0)], None)

        await retrieval.retrieve_passage(_UID, "I'm scared", _NO_TAGS_RESULT)

        scroll_mock.assert_awaited_once()
        call_kwargs = scroll_mock.await_args.kwargs
        assert call_kwargs["collection_name"] == config.settings.qdrant_collection_name
        match_values = call_kwargs["scroll_filter"].must[0].match.any
        assert set(match_values) == {"faith", "hope", "love"}

    @pytest.mark.asyncio
    async def test_fallback_is_not_filtered_against_sent_history(
        self, recent_passages_mock, query_points_mock, scroll_mock, fixed_random_choice
    ) -> None:
        # The fallback is deliberately allowed to repeat passages, so that the fallback pool is never empty. 
        # This test ensures that the fallback pool is not filtered against the sent history.
        recent_passages_mock.return_value = [SentPassage(passage_reference="Philippians 4:13", sent_at=datetime.now())]
        query_points_mock.return_value = SimpleNamespace(points=[_point("Psalm 23:4", 0.1)])
        scroll_mock.return_value = ([_point("Philippians 4:13", 1.0)], None)

        passage = await retrieval.retrieve_passage(_UID, "I'm scared", _NO_TAGS_RESULT)

        assert passage.reference == "Philippians 4:13"
        assert passage.is_fallback is True

    @pytest.mark.asyncio
    async def test_raises_if_fallback_pool_is_empty(
        self, recent_passages_mock, query_points_mock, scroll_mock
    ) -> None:
        query_points_mock.return_value = SimpleNamespace(points=[_point("Psalm 23:4", 0.1)])
        scroll_mock.return_value = ([], None)

        with pytest.raises(RuntimeError, match="fallback pool must never be empty"):
            await retrieval.retrieve_passage(_UID, "I'm scared", _NO_TAGS_RESULT)
