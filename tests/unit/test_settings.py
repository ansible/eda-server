#  Copyright 2024 Red Hat, Inc.
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

import pytest
from django.core.exceptions import ImproperlyConfigured
from dynaconf import Dynaconf

from aap_eda.core.enums import RulebookProcessLogLevel
from aap_eda.settings import core, defaults
from aap_eda.settings.post_load import (
    get_boolean,
    get_rulebook_process_log_level,
    post_loading,
)


@pytest.fixture
def mock_settings():
    mock_settings = Dynaconf(settings_files=[defaults.__file__, core.__file__])
    mock_settings.SECRET_KEY = "secret"
    return mock_settings


@pytest.mark.parametrize(
    "value,expected",
    [
        ("debug", RulebookProcessLogLevel.DEBUG),
        ("info", RulebookProcessLogLevel.INFO),
        ("error", RulebookProcessLogLevel.ERROR),
        ("-v", RulebookProcessLogLevel.INFO),
        ("-vv", RulebookProcessLogLevel.DEBUG),
        (None, RulebookProcessLogLevel.ERROR),
    ],
)
def test_rulebook_log_level(mock_settings, value, expected):
    mock_settings.ANSIBLE_RULEBOOK_LOG_LEVEL = value

    result = get_rulebook_process_log_level(mock_settings)

    assert result == expected


def test_rulebook_log_level_invalid(mock_settings):
    mock_settings.ANSIBLE_RULEBOOK_LOG_LEVEL = "invalid"
    with pytest.raises(ImproperlyConfigured):
        get_rulebook_process_log_level(mock_settings)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("true", True),
        ("True", True),
        ("False", False),
        ("false", False),
        ("yes", True),
        ("no", False),
        ("1", True),
        ("0", False),
        ("", False),
        ("anything", False),
    ],
)
def test_get_boolean(mock_settings, value, expected):
    mock_settings.DEBUG = value
    result = get_boolean(mock_settings, "DEBUG")
    assert result == expected


def test_get_boolean_exception(mock_settings):
    mock_settings.DEBUG = ["something", "else"]
    with pytest.raises(ImproperlyConfigured):
        get_boolean(mock_settings, "DEBUG")


def test_resource_server_sync(mock_settings):
    mock_settings.RESOURCE_SERVER = {
        "SECRET_KEY": "secret",
        "URL": "https://localhost",
        "VALIDATE_HTTPS": False,
    }
    post_loading(mock_settings)
    # With dispatcherd, sync tasks are scheduled differently
    task_func = "aap_eda.tasks.shared_resources.resync_shared_resources"
    assert task_func in mock_settings.DISPATCHERD_SCHEDULE_TASKS
    assert (
        mock_settings.DISPATCHERD_SCHEDULE_TASKS[task_func]["schedule"] == 900
    )


def test_duplicated_worker_queue(mock_settings):
    mock_settings.RULEBOOK_WORKER_QUEUES = ["activation", "activation"]
    with pytest.raises(ImproperlyConfigured):
        post_loading(mock_settings)


@pytest.mark.parametrize(
    ("name", "value", "expected"),
    [
        (
            "EVENT_STREAM_BASE_URL",
            "https://myhost.com/esbu",
            "https://myhost.com/esbu/",
        ),
        (
            "EVENT_STREAM_BASE_URL",
            "https://myhost.com/esbu/",
            "https://myhost.com/esbu/",
        ),
        ("EVENT_STREAM_BASE_URL", None, None),
        ("EVENT_STREAM_BASE_URL", 20, ImproperlyConfigured),
        ("SESSION_COOKIE_AGE", "20", 20),
        ("SESSION_COOKIE_AGE", 20, 20),
        ("SESSION_COOKIE_AGE", "not number", ImproperlyConfigured),
        ("RULEBOOK_QUEUE_NAME", " act ", "act"),
        ("RULEBOOK_QUEUE_NAME", ["name"], ImproperlyConfigured),
        ("RULEBOOK_QUEUE_NAME", 20, ImproperlyConfigured),
        ("ALLOWED_HOSTS", "h1,h2", ["h1", "h2"]),
        ("ALLOWED_HOSTS", ["h1", "h2"], ["h1", "h2"]),
        ("ALLOWED_HOSTS", 20, ImproperlyConfigured),
        ("PODMAN_EXTRA_ARGS", {"opt": "val"}, {"opt": "val"}),
        ("PODMAN_EXTRA_ARGS", "opt=val", ImproperlyConfigured),
        ("RESOURCE_JWT_USER_ID", " eda ", "eda"),
        ("RESOURCE_JWT_USER_ID", ["eda"], ImproperlyConfigured),
    ],
)
def test_types(mock_settings, name, value, expected):
    mock_settings[name] = value
    if expected == ImproperlyConfigured:
        with pytest.raises(ImproperlyConfigured):
            post_loading(mock_settings)
    else:
        post_loading(mock_settings)
        assert mock_settings[name] == expected


def test_optional_type_exception_msg(mock_settings):
    """Test exception message when an optional type error occurs."""
    mock_settings[
        "WEBSOCKET_SSL_VERIFY"
    ] = 123  # Use invalid type instead of string
    with pytest.raises(
        ImproperlyConfigured,
        match="WEBSOCKET_SSL_VERIFY setting must be a bool or str",
    ):
        post_loading(mock_settings)


def test_union_type_exception_msg(mock_settings):
    """Test exception message when a union type error occurs."""
    mock_settings["WEBSOCKET_SSL_VERIFY"] = 123
    with pytest.raises(
        ImproperlyConfigured,
        match="WEBSOCKET_SSL_VERIFY setting must be a bool or str",
    ):
        post_loading(mock_settings)


def test_allow_local_resource_management(mock_settings):
    # default is False
    assert mock_settings.ALLOW_LOCAL_RESOURCE_MANAGEMENT is False
