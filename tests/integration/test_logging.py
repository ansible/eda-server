import importlib
import subprocess
import time

import pytest

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


def test_worker_startup_logs():
    """
    Test that starting workers produce the expected startup message.
    """
    command = ["aap-eda-manage", "rqworker", "--help"]
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
