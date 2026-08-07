"""
Tests for the /comfort classification call (K-03).

These mock the OpenRouter HTTP call and test our own parsing/rejection logic — a real
model's judgment isn't deterministic enough to assert on in an automated suite. The tests
described in the K-03 story ("message with self-harm language returns is_crisis: True with
sensible tags", etc.) are exercised here via canned responses standing in for what a real
model would plausibly return for each scenario.
"""

import json
from unittest.mock import AsyncMock

import pytest

from commands.comfort import classifier
from commands.comfort.models import ClassificationResult, EmotionalTag, SituationalTag


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content


class _FakeChoice:
    def __init__(self, content: str):
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content: str):
        self.choices = [_FakeChoice(content)]


def _mock_llm_response(monkeypatch, content: dict) -> None:
    fake_completion = _FakeCompletion(json.dumps(content))
    monkeypatch.setattr(classifier.client.chat.completions, "create", AsyncMock(return_value=fake_completion))


class TestClassify:
    @pytest.mark.asyncio
    async def test_crisis_message_returns_populated_tags(self, monkeypatch) -> None:
        _mock_llm_response(
            monkeypatch,
            {"is_crisis": True, "emotional_tags": ["despair", "hopelessness"], "situational_tags": ["bereavement"]},
        )
        result = await classifier.classify("I don't want to be here anymore after losing him.", "test-session")

        assert result.is_crisis is True
        assert result.emotional_tags == [EmotionalTag.DESPAIR, EmotionalTag.HOPELESSNESS]
        assert result.situational_tags == [SituationalTag.BEREAVEMENT]

    @pytest.mark.asyncio
    async def test_clear_emotional_content_returns_recognized_tags(self, monkeypatch) -> None:
        _mock_llm_response(
            monkeypatch,
            {"is_crisis": False, "emotional_tags": ["joy", "gratitude"], "situational_tags": []},
        )
        result = await classifier.classify("Today was such a good day, I'm so thankful.", "test-session")

        assert result.is_crisis is False
        assert result.emotional_tags == [EmotionalTag.JOY, EmotionalTag.GRATITUDE]
        assert result.situational_tags == []

    @pytest.mark.asyncio
    async def test_ambiguous_message_returns_empty_emotional_tags_without_error(self, monkeypatch) -> None:
        _mock_llm_response(monkeypatch, {"is_crisis": False, "emotional_tags": [], "situational_tags": []})
        result = await classifier.classify("ok", "test-session")

        assert result.is_crisis is False
        assert result.emotional_tags == []
        assert result.situational_tags == []

    @pytest.mark.asyncio
    async def test_unrecognized_tag_value_is_dropped_not_propagated(self, monkeypatch) -> None:
        _mock_llm_response(
            monkeypatch,
            {
                "is_crisis": False,
                "emotional_tags": ["joy", "not_a_real_tag"],
                "situational_tags": ["job_loss", "not_a_real_situation"],
            },
        )
        result = await classifier.classify("A mixed message.", "test-session")

        assert result.emotional_tags == [EmotionalTag.JOY]
        assert result.situational_tags == [SituationalTag.JOB_LOSS]

    @pytest.mark.asyncio
    async def test_malformed_response_missing_is_crisis_raises(self, monkeypatch) -> None:
        _mock_llm_response(monkeypatch, {"emotional_tags": [], "situational_tags": []})

        with pytest.raises(KeyError):
            await classifier.classify("Some text.", "test-session")

    def test_classification_result_structurally_requires_is_crisis(self) -> None:
        # No path can construct a result without is_crisis — it's a required positional
        # field, not defaulted, so tags can never be returned without it being determined.
        with pytest.raises(TypeError):
            ClassificationResult()  # type: ignore[call-arg]

    @pytest.mark.asyncio
    async def test_spanish_message_classifies_correctly(self, monkeypatch) -> None:
        # Same canned-response approach as the other tests here. This exercises our
        # parsing, not a real model's actual judgment on Spanish input.
        _mock_llm_response(
            monkeypatch,
            {"is_crisis": False, "emotional_tags": ["grief", "sadness"], "situational_tags": ["bereavement"]},
        )
        result = await classifier.classify("Perdí a mi mamá y no sé cómo seguir adelante.", "test-session")

        assert result.is_crisis is False
        assert result.emotional_tags == [EmotionalTag.GRIEF, EmotionalTag.SADNESS]
        assert result.situational_tags == [SituationalTag.BEREAVEMENT]

    @pytest.mark.asyncio
    async def test_system_prompt_instructs_multilingual_classification(self, monkeypatch) -> None:
        mock = AsyncMock(return_value=_FakeCompletion(json.dumps({"is_crisis": False})))
        monkeypatch.setattr(classifier.client.chat.completions, "create", mock)
        await classifier.classify("Some text.", "test-session")

        _, kwargs = mock.call_args
        system_message = next(m["content"] for m in kwargs["messages"] if m["role"] == "system")
        assert "any language" in system_message
        assert "Spanish" in system_message
