"""
Tests /comfort's Langfuse tracing helper. These tests verify the no-op path plus the metadata-passing contract against a fake client, not against a real Langfuse instance.
"""

from unittest.mock import MagicMock

import pytest

from commands.comfort import tracing


class TestTracedNoOp:
    def test_yields_none_when_unconfigured(self) -> None:
        assert tracing.client is None
        with tracing.traced("comfort.some_step") as span:
            assert span is None

    def test_body_still_executes_when_unconfigured(self) -> None:
        ran = False
        with tracing.traced("comfort.some_step"):
            ran = True
        assert ran is True

    def test_exceptions_inside_the_block_still_propagate(self) -> None:
        with pytest.raises(ValueError, match="boom"):
            with tracing.traced("comfort.some_step"):
                raise ValueError("boom")


class TestTracedWithConfiguredClient:
    @pytest.fixture
    def fake_client(self, monkeypatch):
        span = MagicMock()
        fake = MagicMock()
        fake.start_as_current_observation.return_value.__enter__.return_value = span
        monkeypatch.setattr(tracing, "client", fake)
        return fake, span

    def test_starts_a_generation_with_the_given_name_and_model(self, fake_client) -> None:
        fake, _ = fake_client
        with tracing.traced("comfort.embed", as_type="generation", model="text-embedding-3-small"):
            pass

        fake.start_as_current_observation.assert_called_once_with(
            as_type="generation", name="comfort.embed", model="text-embedding-3-small", metadata=None
        )

    def test_starts_a_span_without_a_model_kwarg(self, fake_client) -> None:
        fake, _ = fake_client
        with tracing.traced("comfort.qdrant_query_points", k=40):
            pass

        fake.start_as_current_observation.assert_called_once_with(
            as_type="span", name="comfort.qdrant_query_points", metadata={"k": 40}
        )

    def test_caller_can_update_metadata_on_the_yielded_span(self, fake_client) -> None:
        _, span = fake_client
        with tracing.traced("comfort.retrieve_passage") as yielded_span:
            assert yielded_span is not None
            yielded_span.update(metadata={"outcome": "match"})

        span.update.assert_called_once_with(metadata={"outcome": "match"})
