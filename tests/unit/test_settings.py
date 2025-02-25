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
from aap_eda.settings import constants, defaults
from aap_eda.settings.defaults import (
    DEFAULT_QUEUE_TIMEOUT,
    DEFAULT_RULEBOOK_QUEUE_TIMEOUT,
)
from aap_eda.settings.post_load import (
    get_boolean,
    get_rq_queues,
    get_rulebook_process_log_level,
    post_loading,
)


@pytest.fixture
def mock_settings():
    settings = Dynaconf(settings_files=[defaults.__file__, constants.__file__])
    settings.SECRET_KEY = "secret"
    return settings


@pytest.fixture
def redis_settings(mock_settings):
    mock_settings.REDIS_DB = constants.DEFAULT_REDIS_DB
    mock_settings.REDIS_USER = defaults.MQ_USER
    mock_settings.REDIS_USER_PASSWORD = defaults.MQ_USER_PASSWORD
    mock_settings.REDIS_UNIX_SOCKET_PATH = defaults.MQ_UNIX_SOCKET_PATH
    mock_settings.REDIS_HOST = defaults.MQ_HOST
    mock_settings.REDIS_PORT = defaults.MQ_PORT
    mock_settings.REDIS_TLS = defaults.MQ_TLS
    mock_settings.REDIS_CLIENT_KEY_PATH = defaults.MQ_CLIENT_KEY_PATH
    mock_settings.REDIS_CLIENT_CACERT_PATH = defaults.MQ_CLIENT_CACERT_PATH
    mock_settings.REDIS_CLIENT_CERT_PATH = defaults.MQ_CLIENT_CERT_PATH
    mock_settings.RULEBOOK_WORKER_QUEUES = ["activation"]
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


def test_rq_queues_with_unix_socket_path(redis_settings):
    redis_settings.REDIS_UNIX_SOCKET_PATH = "path/to/socket"
    redis_settings.RULEBOOK_WORKER_QUEUES = ["activation-node1"]

    queues = get_rq_queues(redis_settings)
    assert "default" in queues
    assert queues["default"]["UNIX_SOCKET_PATH"] == "path/to/socket"
    assert queues["default"]["DEFAULT_TIMEOUT"] == DEFAULT_QUEUE_TIMEOUT
    assert "activation-node1" in queues
    assert queues["activation-node1"]["UNIX_SOCKET_PATH"] == "path/to/socket"
    assert (
        queues["activation-node1"]["DEFAULT_TIMEOUT"]
        == DEFAULT_RULEBOOK_QUEUE_TIMEOUT
    )
    assert "activation" not in queues


def test_rq_queues_default_configuration(redis_settings, redis_parameters):
    # Get the host and port from the test redis parameters in case the
    # test is being run using an external redis.
    # We explicitly check for None as the parameters may exist with a value of
    # None.
    host = redis_parameters.get("host")
    if host is None:
        host = "localhost"
    port = redis_parameters.get("port")
    if port is None:
        port = 6379

    for key, val in redis_parameters.items():
        redis_settings.set(key, val)
    queues = get_rq_queues(redis_settings)
    assert queues["default"]["HOST"] == host
    assert queues["default"]["PORT"] == port
    assert queues["default"]["DEFAULT_TIMEOUT"] == DEFAULT_QUEUE_TIMEOUT
    assert queues["activation"]["HOST"] == host
    assert queues["activation"]["PORT"] == port
    assert (
        queues["activation"]["DEFAULT_TIMEOUT"]
        == DEFAULT_RULEBOOK_QUEUE_TIMEOUT
    )


def test_rq_queues_custom_host(redis_settings):
    redis_settings.REDIS_HOST = "custom-host"
    queues = get_rq_queues(redis_settings)

    assert queues["default"]["HOST"] == "custom-host"
    assert queues["default"]["PORT"] == 6379
    assert queues["default"]["DEFAULT_TIMEOUT"] == DEFAULT_QUEUE_TIMEOUT
    assert queues["activation"]["HOST"] == "custom-host"
    assert queues["activation"]["PORT"] == 6379
    assert (
        queues["activation"]["DEFAULT_TIMEOUT"]
        == DEFAULT_RULEBOOK_QUEUE_TIMEOUT
    )


def test_rq_queues_custom_host_multiple_queues(redis_settings):
    redis_settings.RULEBOOK_WORKER_QUEUES = [
        "activation-node1",
        "activation-node2",
    ]
    redis_settings.REDIS_HOST = "custom-host"
    redis_settings.REDIS_USER_PASSWORD = "password"
    redis_settings.REDIS_CLIENT_CERT_PATH = "somepath"
    queues = get_rq_queues(redis_settings)
    assert queues["default"]["HOST"] == "custom-host"
    assert queues["default"]["PORT"] == 6379
    assert queues["default"]["DEFAULT_TIMEOUT"] == DEFAULT_QUEUE_TIMEOUT
    assert queues["activation-node1"]["HOST"] == "custom-host"
    assert queues["activation-node1"]["PORT"] == 6379
    assert (
        queues["activation-node1"]["DEFAULT_TIMEOUT"]
        == DEFAULT_RULEBOOK_QUEUE_TIMEOUT
    )
    assert queues["activation-node2"]["HOST"] == "custom-host"
    assert queues["activation-node2"]["PORT"] == 6379
    assert (
        queues["activation-node2"]["DEFAULT_TIMEOUT"]
        == DEFAULT_RULEBOOK_QUEUE_TIMEOUT
    )
    assert queues["default"]["PASSWORD"] == "password"
    assert (
        queues["default"]["REDIS_CLIENT_KWARGS"]["ssl_certfile"] == "somepath"
    )
    assert queues["activation-node1"]["PASSWORD"] == "password"
    assert (
        queues["activation-node1"]["REDIS_CLIENT_KWARGS"]["ssl_certfile"]
        == "somepath"
    )
    assert "activation" not in queues


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
    sync_task = {
        "func": "aap_eda.tasks.shared_resources.resync_shared_resources",  # noqa: E501
        "interval": 900,
        "id": "resync_shared_resources",
    }
    assert sync_task in mock_settings.RQ_PERIODIC_JOBS


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
