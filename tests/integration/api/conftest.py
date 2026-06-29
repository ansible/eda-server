"""Shared test configuration for API integration tests."""

import pytest
from django.test.utils import override_settings


@pytest.fixture(autouse=True)
def disable_trusted_proxy_validation_for_tests(request):
    """
    Automatically disable X-Trusted-Proxy header validation for all tests
    EXCEPT the specific trusted proxy validation tests.

    This allows event stream tests to run without needing the X-Trusted-Proxy
    header from Gateway/Envoy Proxy.

    The trusted proxy validation tests (test_event_stream_trusted_proxy.py)
    are excluded from this fixture and will use the default setting (True)
    to actually test the validation.
    """
    # Skip the override for trusted proxy validation tests (exact path match)
    if request.node.nodeid.startswith(
        "tests/integration/api/test_event_stream_trusted_proxy.py::"
    ):
        yield
        return

    # Disable validation for all other tests
    with override_settings(EVENT_STREAM_REQUIRE_TRUSTED_PROXY=False):
        yield
