from unittest.mock import MagicMock, patch

import gspread
import pytest

from commands.information.cache import CachedInformationAdapter
from commands.information.google_sheets import GoogleSheetsInformationAdapter
from commands.information.models import InformationTopic, InformationUnavailableError


def _topic(**overrides) -> dict:
    defaults = dict(key="mass_times", label_en="Mass Times", body_en="Sundays at 9am.", order=1)
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# CachedInformationAdapter
# ---------------------------------------------------------------------------

class TestCachedInformationAdapter:
    def _make_inner(self, topics: list[InformationTopic] | None = None) -> MagicMock:
        inner = MagicMock()
        inner.list_topics.return_value = topics if topics is not None else [InformationTopic(**_topic())]
        return inner

    def test_calls_inner_on_first_request(self):
        inner = self._make_inner()
        adapter = CachedInformationAdapter(inner, ttl_seconds=60)
        adapter.list_topics()
        inner.list_topics.assert_called_once()

    def test_returns_cached_result_on_second_request(self):
        inner = self._make_inner()
        adapter = CachedInformationAdapter(inner, ttl_seconds=60)
        first = adapter.list_topics()
        second = adapter.list_topics()
        assert first is second
        inner.list_topics.assert_called_once()

    def test_refreshes_after_ttl_expires(self):
        inner = self._make_inner()
        adapter = CachedInformationAdapter(inner, ttl_seconds=60)

        with patch("commands.information.cache.time.time", return_value=0.0):
            adapter.list_topics()

        with patch("commands.information.cache.time.time", return_value=61.0):
            adapter.list_topics()

        assert inner.list_topics.call_count == 2

    def test_does_not_refresh_before_ttl_expires(self):
        inner = self._make_inner()
        adapter = CachedInformationAdapter(inner, ttl_seconds=60)

        with patch("commands.information.cache.time.time", return_value=0.0):
            adapter.list_topics()

        with patch("commands.information.cache.time.time", return_value=59.0):
            adapter.list_topics()

        inner.list_topics.assert_called_once()

    def test_propagates_information_unavailable_error(self):
        inner = MagicMock()
        inner.list_topics.side_effect = InformationUnavailableError("unreachable")
        adapter = CachedInformationAdapter(inner, ttl_seconds=60)
        with pytest.raises(InformationUnavailableError):
            adapter.list_topics()

    def test_leaves_cache_empty_when_inner_raises(self):
        inner = MagicMock()
        inner.list_topics.side_effect = InformationUnavailableError("unreachable")
        adapter = CachedInformationAdapter(inner, ttl_seconds=60)

        with pytest.raises(InformationUnavailableError):
            adapter.list_topics()

        inner.list_topics.side_effect = None
        inner.list_topics.return_value = [InformationTopic(**_topic())]
        result = adapter.list_topics()
        assert result == [InformationTopic(**_topic())]

    def test_get_topic_returns_matching_topic_from_cached_list(self):
        topics = [InformationTopic(**_topic(key="a")), InformationTopic(**_topic(key="b"))]
        inner = self._make_inner(topics)
        adapter = CachedInformationAdapter(inner, ttl_seconds=60)
        result = adapter.get_topic("b")
        assert result is topics[1]

    def test_get_topic_returns_none_when_key_not_found(self):
        inner = self._make_inner([InformationTopic(**_topic(key="a"))])
        adapter = CachedInformationAdapter(inner, ttl_seconds=60)
        assert adapter.get_topic("missing") is None

    def test_get_topic_uses_the_cache_not_a_fresh_fetch(self):
        inner = self._make_inner([InformationTopic(**_topic(key="a"))])
        adapter = CachedInformationAdapter(inner, ttl_seconds=60)
        adapter.list_topics()
        adapter.get_topic("a")
        inner.list_topics.assert_called_once()


# ---------------------------------------------------------------------------
# GoogleSheetsInformationAdapter
# ---------------------------------------------------------------------------

def _mock_spreadsheet(rows: list[dict]) -> MagicMock:
    worksheet = MagicMock()
    worksheet.get_all_records.return_value = rows
    spreadsheet = MagicMock()
    spreadsheet.worksheet.return_value = worksheet
    return spreadsheet


@pytest.fixture
def adapter() -> GoogleSheetsInformationAdapter:
    a = GoogleSheetsInformationAdapter(spreadsheet_id="sheet-id", credentials_path="creds.json")
    a._client = MagicMock()
    return a


def _patch_open(adapter: GoogleSheetsInformationAdapter, spreadsheet: MagicMock) -> None:
    adapter._client.open_by_key.return_value = spreadsheet  # type: ignore[union-attr]


class TestListTopics:
    def test_parses_valid_rows_sorted_by_order(self, adapter):
        rows = [
            {"topic_key": "mass_times", "label_en": "Mass Times", "label_es": "Horarios de Misa",
             "body_en": "Sundays at 9am.", "body_es": "Domingos a las 9am.", "order": 2},
            {"topic_key": "baptism", "label_en": "Baptism", "label_es": "Bautismo",
             "body_en": "Contact the office.", "body_es": "Contacta la oficina.", "order": 1},
        ]
        _patch_open(adapter, _mock_spreadsheet(rows))
        topics = adapter.list_topics()
        assert [t.key for t in topics] == ["baptism", "mass_times"]

    def test_reads_the_configured_tab(self, adapter):
        spreadsheet = _mock_spreadsheet([])
        _patch_open(adapter, spreadsheet)
        with patch("commands.information.google_sheets.settings") as mock_settings:
            mock_settings.information_topics_tab = "Custom Tab"
            adapter.list_topics()
        spreadsheet.worksheet.assert_called_once_with("Custom Tab")

    def test_skips_row_with_missing_required_field(self, adapter):
        rows = [
            {"topic_key": "", "label_en": "Mass Times", "body_en": "Sundays at 9am.", "order": 1},
            {"topic_key": "baptism", "label_en": "Baptism", "body_en": "Contact the office.", "order": 2},
        ]
        _patch_open(adapter, _mock_spreadsheet(rows))
        topics = adapter.list_topics()
        assert [t.key for t in topics] == ["baptism"]

    def test_skips_row_with_invalid_order(self, adapter):
        rows = [
            {"topic_key": "mass_times", "label_en": "Mass Times", "body_en": "Sundays.", "order": "not-a-number"},
            {"topic_key": "baptism", "label_en": "Baptism", "body_en": "Contact the office.", "order": 1},
        ]
        _patch_open(adapter, _mock_spreadsheet(rows))
        topics = adapter.list_topics()
        assert [t.key for t in topics] == ["baptism"]

    def test_skips_row_with_missing_order(self, adapter):
        rows = [{"topic_key": "mass_times", "label_en": "Mass Times", "body_en": "Sundays."}]
        _patch_open(adapter, _mock_spreadsheet(rows))
        assert adapter.list_topics() == []

    def test_order_zero_is_a_valid_position(self, adapter):
        rows = [{"topic_key": "mass_times", "label_en": "Mass Times", "body_en": "Sundays.", "order": 0}]
        _patch_open(adapter, _mock_spreadsheet(rows))
        topics = adapter.list_topics()
        assert [t.key for t in topics] == ["mass_times"]

    def test_missing_label_es_and_body_es_default_to_empty(self, adapter):
        rows = [{"topic_key": "mass_times", "label_en": "Mass Times", "body_en": "Sundays.", "order": 1}]
        _patch_open(adapter, _mock_spreadsheet(rows))
        topics = adapter.list_topics()
        assert topics[0].label_es == ""
        assert topics[0].body_es == ""

    def test_empty_sheet_returns_empty_list(self, adapter):
        _patch_open(adapter, _mock_spreadsheet([]))
        assert adapter.list_topics() == []

    def test_missing_tab_raises_information_unavailable_error(self, adapter):
        spreadsheet = MagicMock()
        spreadsheet.worksheet.side_effect = gspread.WorksheetNotFound
        _patch_open(adapter, spreadsheet)
        with pytest.raises(InformationUnavailableError):
            adapter.list_topics()

    def test_generic_api_failure_raises_information_unavailable_error(self, adapter):
        adapter._client.open_by_key.side_effect = Exception("network down")  # type: ignore[union-attr]
        with pytest.raises(InformationUnavailableError):
            adapter.list_topics()

    def test_get_all_records_failure_raises_information_unavailable_error(self, adapter):
        spreadsheet = _mock_spreadsheet([])
        spreadsheet.worksheet.return_value.get_all_records.side_effect = Exception("quota exceeded")
        _patch_open(adapter, spreadsheet)
        with pytest.raises(InformationUnavailableError):
            adapter.list_topics()

    def test_get_topic_returns_matching_topic(self, adapter):
        rows = [{"topic_key": "mass_times", "label_en": "Mass Times", "body_en": "Sundays.", "order": 1}]
        _patch_open(adapter, _mock_spreadsheet(rows))
        result = adapter.get_topic("mass_times")
        assert result is not None
        assert result.key == "mass_times"

    def test_get_topic_returns_none_when_not_found(self, adapter):
        rows = [{"topic_key": "mass_times", "label_en": "Mass Times", "body_en": "Sundays.", "order": 1}]
        _patch_open(adapter, _mock_spreadsheet(rows))
        assert adapter.get_topic("missing") is None
