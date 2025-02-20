import importlib
import subprocess
import time

import pytest
from django.test import override_settings

from aap_eda import asgi, wsgi


@pytest.mark.django_db
@pytest.mark.parametrize("module", [wsgi, asgi])
def test_http_startup_logging(caplog_factory, module):
    """
    Test that wsgi and asgi logs the expected startup message.
    """
    caplog = caplog_factory(module.logger)

    # Re-importing to capture logs during repeated test runs
    importlib.reload(module)

    assert "Starting eda-server" in caplog.text


@pytest.mark.django_db
@pytest.mark.parametrize("module", [wsgi, asgi])
def test_http_startup_logging_disabled(caplog_factory, module):
    """
    Test that wsgi and asgi does not log the startup message when disabled.
    """
    caplog = caplog_factory(module.logger)
    with override_settings(STARTUP_LOGGING_ENABLED=False):
        importlib.reload(module)
    assert "Starting eda-server" not in caplog.text


@pytest.mark.parametrize(
    "command",
    [
        ["aap-eda-manage", "rqworker", "--help"],
        [
            "gunicorn",
            "aap_eda.wsgi:application",
            "--bind",
            "127.0.0.1:8009",
        ],
        [
            "daphne",
            "-b",
            "127.0.0.1",
            "-p",
            "8009",
            "aap_eda.asgi:application",
        ],
    ],
)
def test_worker_startup_logs(command):
    """
    Test that starting workers produce the expected startup message.
    """
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    time.sleep(3)
    process.terminate()
    stdout, stderr = process.communicate(timeout=3)

    assert "Starting eda-server" in stderr
