#  Copyright 2025 Red Hat, Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import json
from datetime import datetime, timezone
from unittest.mock import ANY, MagicMock, patch

import pytest
from django.db import connection

from aap_eda.analytics.collector import AnalyticsCollector, gather


@pytest.fixture
def mock_settings():
    """Mock application settings with proper attribute access."""

    class Settings:
        INSIGHTS_TRACKING_STATE = True
        AUTOMATION_ANALYTICS_LAST_GATHER = None
        AUTOMATION_ANALYTICS_LAST_ENTRIES = '{"key": "value"}'

    return Settings()


@pytest.fixture
def collector():
    collector = AnalyticsCollector()
    collector.logger = MagicMock()
    return collector


@patch("aap_eda.analytics.collector.flag_enabled")
@patch("aap_eda.analytics.collector.AnalyticsCollector")
def test_gather_when_enabled(mock_collector_cls, mock_flag_enabled):
    """Test gather function when FEATURE_EDA_ANALYTICS_ENABLED
    is set to True"""
    mock_flag_enabled.return_value = True
    mock_collector_cls.return_value = MagicMock()
    mock_logger = MagicMock()

    result = gather(
        collection_type="manual",
        since=datetime(2023, 1, 1),
        until=datetime(2023, 1, 2),
        logger=mock_logger,
    )

    mock_flag_enabled.assert_called_once_with("FEATURE_EDA_ANALYTICS_ENABLED")
    mock_collector_cls.assert_called_once_with(
        collector_module=ANY,
        collection_type="manual",
        logger=mock_logger,
    )
    assert result is not None


@patch("aap_eda.analytics.collector.flag_enabled")
def test_gather_when_disabled(mock_flag_enabled):
    """Test gather function when FEATURE_EDA_ANALYTICS_ENABLED
    is set to False"""
    mock_flag_enabled.return_value = False
    mock_logger = MagicMock()

    result = gather(logger=mock_logger)

    mock_logger.info.assert_called_once_with(
        "FEATURE_EDA_ANALYTICS_ENABLED is set to False."
    )
    assert result is None


@pytest.mark.django_db
@patch("aap_eda.analytics.collector.flag_enabled")
@patch("aap_eda.analytics.collector.AnalyticsCollector")
def test_gather_uses_default_logger(mock_collector_cls, mock_flag_enabled):
    mock_flag_enabled.return_value = True

    with patch(
        "aap_eda.analytics.collector.logging.getLogger"
    ) as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        gather()

        mock_get_logger.assert_called_once_with("aap_eda.analytics")
        mock_logger.info.assert_not_called()


@pytest.mark.django_db
def test_shipping_enabled_returns_true(collector, mock_settings):
    mock_settings.INSIGHTS_TRACKING_STATE = True
    with patch(
        "aap_eda.analytics.collector.application_settings",
        new=mock_settings,
    ):
        assert collector._is_shipping_configured() is True


@pytest.mark.django_db
def test_shipping_disabled_logs_warning(collector, mock_settings):
    mock_settings.INSIGHTS_TRACKING_STATE = False
    with patch(
        "aap_eda.analytics.collector.application_settings",
        new=mock_settings,
    ):
        assert collector._is_shipping_configured() is False
        collector.logger.warning.assert_called_once_with(
            "Insights for Event Driven Ansible is not enabled."
        )


@pytest.mark.django_db
def test_last_gathering_with_valid_time(collector, mock_settings):
    test_time = "2023-01-01T12:00:00+00:00"
    mock_settings.AUTOMATION_ANALYTICS_LAST_GATHER = test_time
    with patch(
        "aap_eda.analytics.collector.application_settings",
        new=mock_settings,
    ):
        result = collector._last_gathering()
        assert result == datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)


@pytest.mark.django_db
def test_last_gathering_with_missing_time(collector, mock_settings):
    with patch(
        "aap_eda.analytics.collector.application_settings",
        new=mock_settings,
    ):
        assert collector._last_gathering() is None


@pytest.mark.django_db
def test_save_last_gather_persists_iso_format(collector, mock_settings):
    test_time = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
    collector.gather_until = test_time
    with patch(
        "aap_eda.analytics.collector.application_settings",
        new=mock_settings,
    ):
        collector._save_last_gather()
        assert (
            mock_settings.AUTOMATION_ANALYTICS_LAST_GATHER
            == "2023-01-01T12:00:00+00:00"
        )


@pytest.mark.django_db
def test_load_entries_with_valid_json(collector, mock_settings):
    with patch(
        "aap_eda.analytics.collector.application_settings",
        new=mock_settings,
    ):
        result = collector._load_last_gathered_entries()
        assert result == {"key": "value"}


@pytest.mark.django_db
def test_load_entries_with_invalid_json_logs_error(collector, mock_settings):
    mock_settings.AUTOMATION_ANALYTICS_LAST_ENTRIES = "invalid_json"
    with patch(
        "aap_eda.analytics.collector.application_settings",
        new=mock_settings,
    ):
        result = collector._load_last_gathered_entries()
        assert result == {}
        collector.logger.error.assert_called_once_with(
            "Failed to load last entries: Expecting value: "
            "line 1 column 1 (char 0)"
        )


@pytest.mark.django_db
def test_save_entries_persists_valid_json(collector, mock_settings):
    test_data = {"new_key": datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)}
    with patch(
        "aap_eda.analytics.collector.application_settings",
        new=mock_settings,
    ):
        collector._save_last_gathered_entries(test_data)
        saved_data = json.loads(
            mock_settings.AUTOMATION_ANALYTICS_LAST_ENTRIES
        )
        assert saved_data["new_key"] == "2023-01-01T12:00:00Z"


def test_db_connection_returns_django_connection():
    assert AnalyticsCollector.db_connection() is connection


def test_package_class_returns_correct_type():
    from aap_eda.analytics import package

    assert AnalyticsCollector._package_class() is package.Package
