"""
Tests /comfort's Langfuse tracing helper: the `traced()` context manager's
call-shape contract against a fake client (not a real Langfuse instance), 
and the `_mask` allow-list function's redaction behavior.
"""

from unittest.mock import MagicMock

import pytest

from commands.comfort import tracing


class TestTraced:
    @pytest.fixture
    def fake_client(self, monkeypatch):
        span = MagicMock()
        fake = MagicMock()
        fake.start_as_current_observation.return_value.__enter__.return_value = span
        monkeypatch.setattr(tracing, "client", fake)
        return fake, span

    def test_starts_a_span_by_default(self, fake_client) -> None:
        fake, _ = fake_client
        with tracing.traced("comfort.retrieve_passage"):
            pass

        fake.start_as_current_observation.assert_called_once_with(
            as_type="span", name="comfort.retrieve_passage", metadata=None
        )

    def test_starts_a_retriever_with_metadata(self, fake_client) -> None:
        fake, _ = fake_client
        with tracing.traced("comfort.qdrant_query_points", as_type="retriever", k=40):
            pass

        fake.start_as_current_observation.assert_called_once_with(
            as_type="retriever", name="comfort.qdrant_query_points", metadata={"k": 40}
        )

    def test_caller_can_update_metadata_on_the_yielded_span(self, fake_client) -> None:
        _, span = fake_client
        with tracing.traced("comfort.retrieve_passage") as yielded_span:
            yielded_span.update(metadata={"outcome": "match"})

        span.update.assert_called_once_with(metadata={"outcome": "match"})

    def test_body_still_executes(self, fake_client) -> None:
        ran = False
        with tracing.traced("comfort.some_step"):
            ran = True
        assert ran is True

    def test_exceptions_inside_the_block_still_propagate(self, fake_client) -> None:
        with pytest.raises(ValueError, match="boom"):
            with tracing.traced("comfort.some_step"):
                raise ValueError("boom")


class TestMask:
    def test_known_safe_dict_passes_through_unchanged(self) -> None:
        data = {"outcome": "match", "candidates_checked": 3, "similarity_score": 0.87}
        assert tracing._mask(data=data) == data

    def test_dict_with_unrecognized_key_is_redacted(self) -> None:
        assert tracing._mask(data={"outcome": "match", "message": "please help me"}) == "[redacted]"

    def test_dict_with_non_primitive_value_is_redacted(self) -> None:
        assert tracing._mask(data={"outcome": {"nested": "value"}}) == "[redacted]"

    def test_string_is_redacted(self) -> None:
        assert tracing._mask(data="some raw prompt or completion text") == "[redacted]"

    def test_none_passes_through_as_none(self) -> None:
        assert tracing._mask(data=None) is None
