from typing import Optional

import pytest

from commands.information.adapter import InformationAdapter
from commands.information.models import InformationTopic


def _topic(**overrides) -> dict:
    defaults = dict(key="mass_times", label_en="Mass Times", body_en="Sundays at 9am.", order=1)
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# InformationTopic validation
# ---------------------------------------------------------------------------

class TestInformationTopic:
    def test_valid_topic_is_constructed(self):
        topic = InformationTopic(**_topic())
        assert topic.key == "mass_times"
        assert topic.label_en == "Mass Times"
        assert topic.body_en == "Sundays at 9am."
        assert topic.order == 1

    def test_missing_key_raises(self):
        with pytest.raises(ValueError):
            InformationTopic(**_topic(key=""))

    def test_missing_label_en_raises(self):
        with pytest.raises(ValueError):
            InformationTopic(**_topic(label_en=""))

    def test_missing_body_en_raises(self):
        with pytest.raises(ValueError):
            InformationTopic(**_topic(body_en=""))

    def test_missing_label_es_and_body_es_is_allowed(self):
        topic = InformationTopic(**_topic())
        assert topic.label_es == ""
        assert topic.body_es == ""

    def test_label_es_and_body_es_can_be_provided(self):
        topic = InformationTopic(**_topic(label_es="Horarios de Misa", body_es="Domingos a las 9am."))
        assert topic.label_es == "Horarios de Misa"
        assert topic.body_es == "Domingos a las 9am."


# ---------------------------------------------------------------------------
# InformationAdapter interface
# ---------------------------------------------------------------------------

class TestInformationAdapter:
    def test_cannot_be_instantiated_directly(self):
        with pytest.raises(TypeError):
            InformationAdapter()  # type: ignore[abstract]

    def test_concrete_subclass_can_implement_both_methods(self):
        class _FakeAdapter(InformationAdapter):
            def list_topics(self) -> list[InformationTopic]:
                return [InformationTopic(**_topic())]

            def get_topic(self, key: str) -> Optional[InformationTopic]:
                return next((t for t in self.list_topics() if t.key == key), None)

        adapter = _FakeAdapter()
        assert adapter.list_topics()[0].key == "mass_times"
        assert adapter.get_topic("mass_times") is not None
        assert adapter.get_topic("missing") is None
