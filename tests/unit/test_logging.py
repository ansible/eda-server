import logging
import platform

from django.conf import settings
from django.test import override_settings

from aap_eda.utils import get_package_version
from aap_eda.utils.logging import SETTINGS_LIST_FOR_LOGGING, startup_logging


@override_settings(SECRET_KEY="some_random_not_so_secret_key")
def test_startup_logging(caplog_factory):
    logger = logging.getLogger(__name__)
    caplog = caplog_factory(logger)
    startup_logging(logger)

    assert "Starting eda-server" in caplog.text
    assert get_package_version("aap-eda") in caplog.text
    assert "Python version" in caplog.text
    assert platform.python_version() in caplog.text
    for setting in SETTINGS_LIST_FOR_LOGGING:
        assert setting in caplog.text
        assert str(getattr(settings, setting)) in caplog.text

    # some assertions to check that sensitive data is not logged
    assert settings.SECRET_KEY not in caplog.text
    database_password = getattr(
        settings.DATABASES["default"], "PASSWORD", None
    )

    if database_password:
        assert database_password not in caplog.text

    for word in ["SECRET", "PASSWORD"]:
        assert word not in caplog.text
