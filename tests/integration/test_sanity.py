from django.conf import settings


def test_debug_enabled_for_testing():
    assert settings.DEBUG is True
