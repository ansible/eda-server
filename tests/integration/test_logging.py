import importlib
import subprocess
import time

import pytest
from django.conf import settings

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
    assert f"HOST: {settings.DB_HOST}" in caplog.text


def test_worker_startup_logs():
    """
    Test that starting workers produce the expected startup message.
    """
    command = ["aap-eda-manage", "rqworker", "--help"]
    timeout = 10
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )

    expected_message = "Starting eda-server"
    found = False
    start_time = time.time()

    while time.time() - start_time < timeout:
        line = process.stderr.readline()
        if expected_message in line:
            found = True
            break

    process.terminate()
    stdout, stderr = process.communicate(timeout=3)

    error_message = (
        f"Expected message '{expected_message}' "
        f"not found in stderr output: {stderr}"
    )
    assert found, error_message
