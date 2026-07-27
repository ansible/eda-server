"""Shared test configuration for API integration tests."""

import pytest
from django.test.utils import override_settings


@pytest.fixture(autouse=True)
def disable_trusted_proxy_validation_for_tests(request):
    """Disable X-Trusted-Proxy header validation for all tests except
    those marked with @pytest.mark.trusted_proxy_validation."""
    if "trusted_proxy_validation" in request.node.keywords:
        yield
        return

    # Disable validation for all other tests
    with override_settings(EVENT_STREAM_REQUIRE_TRUSTED_PROXY=False):
        yield
