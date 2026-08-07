"""
Tests for the /comfort verse-framing call (K-08).

Mocks the OpenRouter chat completion the same way test_classifier.py does. A real
model's exact wording isn't deterministic enough to assert on in an automated suite, so
these test our own request construction and response handling.
"""

from unittest.mock import AsyncMock

import pytest

from commands.comfort import framing

_REFERENCE = "Psalm 23:4"
_VERSE_TEXT = "Test verse text."


class _FakeMessage:
    def __init__(self, content: str | None):
        self.content = content


class _FakeChoice:
    def __init__(self, content: str | None):
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content: str | None):
        self.choices = [_FakeChoice(content)]


def _mock_llm_response(monkeypatch, content: str | None) -> AsyncMock:
    mock = AsyncMock(return_value=_FakeCompletion(content))
    monkeypatch.setattr(framing.client.chat.completions, "create", mock)
    return mock


class TestFramePassage:
    @pytest.mark.asyncio
    async def test_returns_the_reflection_text(self, monkeypatch) -> None:
        _mock_llm_response(monkeypatch, "You are not alone in this moment.")
        reflection = await framing.frame_passage("I'm scared", _REFERENCE, _VERSE_TEXT, "test-session", "en")
        assert reflection == "You are not alone in this moment."

    @pytest.mark.asyncio
    async def test_strips_surrounding_whitespace(self, monkeypatch) -> None:
        _mock_llm_response(monkeypatch, "  A reflection with padding.  \n")
        reflection = await framing.frame_passage("I'm scared", _REFERENCE, _VERSE_TEXT, "test-session", "en")
        assert reflection == "A reflection with padding."

    @pytest.mark.asyncio
    async def test_includes_raw_text_and_verse_in_the_request(self, monkeypatch) -> None:
        mock = _mock_llm_response(monkeypatch, "A reflection.")
        await framing.frame_passage("I'm scared and alone.", _REFERENCE, _VERSE_TEXT, "test-session", "en")

        _, kwargs = mock.call_args
        user_message = next(m["content"] for m in kwargs["messages"] if m["role"] == "user")
        assert "I'm scared and alone." in user_message
        assert _REFERENCE in user_message
        assert _VERSE_TEXT in user_message

    @pytest.mark.asyncio
    async def test_system_prompt_caps_reflection_at_three_sentences(self, monkeypatch) -> None:
        mock = _mock_llm_response(monkeypatch, "A reflection.")
        await framing.frame_passage("I'm scared", _REFERENCE, _VERSE_TEXT, "test-session", "en")

        _, kwargs = mock.call_args
        system_message = next(m["content"] for m in kwargs["messages"] if m["role"] == "system")
        assert "no more than 3 sentences" in system_message

    @pytest.mark.asyncio
    async def test_does_not_ask_for_classification_or_tags(self, monkeypatch) -> None:
        mock = _mock_llm_response(monkeypatch, "A reflection.")
        await framing.frame_passage("I'm scared", _REFERENCE, _VERSE_TEXT, "test-session", "en")

        _, kwargs = mock.call_args
        system_message = next(m["content"] for m in kwargs["messages"] if m["role"] == "system")
        assert "do not classify" in system_message.lower()

    @pytest.mark.asyncio
    async def test_requests_spanish_when_session_language_is_spanish(self, monkeypatch) -> None:
        mock = _mock_llm_response(monkeypatch, "Una reflexión.")
        await framing.frame_passage("Tengo miedo", _REFERENCE, _VERSE_TEXT, "test-session", "es")

        _, kwargs = mock.call_args
        user_message = next(m["content"] for m in kwargs["messages"] if m["role"] == "user")
        assert "Spanish" in user_message

    @pytest.mark.asyncio
    async def test_uses_the_localized_verse_text_passed_in(self, monkeypatch) -> None:
        # framing.py doesn't know about the verse bank's bilingual payload — it just
        # reflects on whatever text the caller (flow.py) already localized.
        mock = _mock_llm_response(monkeypatch, "Una reflexión.")
        await framing.frame_passage("Tengo miedo", "Salmo 23:4", "Texto del verso en español.", "test-session", "es")

        _, kwargs = mock.call_args
        user_message = next(m["content"] for m in kwargs["messages"] if m["role"] == "user")
        assert "Salmo 23:4" in user_message
        assert "Texto del verso en español." in user_message

    @pytest.mark.asyncio
    async def test_no_content_raises(self, monkeypatch) -> None:
        _mock_llm_response(monkeypatch, None)
        with pytest.raises(ValueError):
            await framing.frame_passage("I'm scared", _REFERENCE, _VERSE_TEXT, "test-session", "en")
