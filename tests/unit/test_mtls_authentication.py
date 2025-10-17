"""Unit tests for mTLS authentication functionality."""

import pytest
from rest_framework.exceptions import AuthenticationFailed

from aap_eda.api.event_stream_authentication import MTLSAuthentication


def test_mtls_authentication_valid_exact_match():
    """Test mTLS authentication with exact subject match."""
    auth = MTLSAuthentication(
        subject="CN=server.example.com,O=Test Org,C=US",
        value="CN=server.example.com,O=Test Org,C=US",
    )

    # Should not raise exception
    auth.authenticate()


def test_mtls_authentication_valid_case_insensitive():
    """Test mTLS authentication with case insensitive match."""
    auth = MTLSAuthentication(
        subject="CN=Server.Example.Com,O=Test Org,C=us",
        value="CN=server.example.com,O=Test Org,C=US",
    )

    # Should not raise exception
    auth.authenticate()


def test_mtls_authentication_valid_order_independent():
    """Test mTLS authentication with different attribute order."""
    auth = MTLSAuthentication(
        subject="CN=server.example.com,O=Test Org,C=US",
        value="O=Test Org,CN=server.example.com,C=US",
    )

    # Should not raise exception
    auth.authenticate()


def test_mtls_authentication_valid_whitespace_normalization():
    """Test mTLS authentication with whitespace differences."""
    auth = MTLSAuthentication(
        subject="CN=server.example.com, O=Test Org, C=US",
        value="CN=server.example.com,O=Test Org,C=US",
    )

    # Should not raise exception
    auth.authenticate()


def test_mtls_authentication_valid_wildcard_match():
    """Test mTLS authentication with wildcard pattern."""
    auth = MTLSAuthentication(
        subject="CN=.*\\.example\\.com,O=Test Org",
        value="CN=server.example.com,O=Test Org",
    )

    # Should not raise exception
    auth.authenticate()


def test_mtls_authentication_valid_multiple_wildcards():
    """Test mTLS authentication with multiple wildcard patterns."""
    auth = MTLSAuthentication(
        subject="CN=.*\\..*\\.com,O=.*", value="CN=api.server.com,O=TestOrg"
    )

    # Should not raise exception
    auth.authenticate()


def test_mtls_authentication_invalid_subject_mismatch():
    """Test mTLS authentication with subject mismatch."""
    auth = MTLSAuthentication(
        subject="CN=server.example.com,O=Test Org",
        value="CN=different.example.com,O=Test Org",
    )

    with pytest.raises(AuthenticationFailed) as exc_info:
        auth.authenticate()

    assert "does not match" in str(exc_info.value)
    assert "CN=different.example.com,O=Test Org" in str(exc_info.value)


def test_mtls_authentication_invalid_missing_attribute():
    """Test mTLS authentication with missing required attribute."""
    auth = MTLSAuthentication(
        subject="CN=server.example.com,O=Test Org",
        value="CN=server.example.com",
    )

    with pytest.raises(AuthenticationFailed) as exc_info:
        auth.authenticate()

    assert "does not match" in str(exc_info.value)


def test_mtls_authentication_invalid_wildcard_no_match():
    """Test mTLS authentication with wildcard that doesn't match."""
    auth = MTLSAuthentication(
        subject="CN=.*\\.example\\.com", value="CN=server.different.com"
    )

    with pytest.raises(AuthenticationFailed) as exc_info:
        auth.authenticate()

    assert "does not match" in str(exc_info.value)


def test_mtls_authentication_invalid_dn_format():
    """Test mTLS authentication with invalid DN format."""
    auth = MTLSAuthentication(
        subject="INVALID=test", value="CN=server.example.com"
    )

    with pytest.raises(AuthenticationFailed) as exc_info:
        auth.authenticate()

    assert "does not match" in str(exc_info.value)


def test_mtls_authentication_empty_subject_allowed():
    """Test mTLS authentication with empty subject (should pass)."""
    auth = MTLSAuthentication(subject="", value="CN=server.example.com")

    # Should not raise exception when subject is empty
    auth.authenticate()


def test_mtls_authentication_none_subject_allowed():
    """Test mTLS authentication with None subject (should pass)."""
    auth = MTLSAuthentication(subject=None, value="CN=server.example.com")

    # Should not raise exception when subject is None
    auth.authenticate()


def test_validate_subject_method_direct():
    """Test validate_subject method directly."""
    auth = MTLSAuthentication(subject="CN=test", value="CN=test")

    # Test valid cases
    assert auth.validate_subject("CN=test", "CN=test") is True
    assert auth.validate_subject("CN=Test", "CN=test") is True
    assert (
        auth.validate_subject("CN=.*\\.example\\.com", "CN=api.example.com")
        is True
    )

    # Test invalid cases
    assert auth.validate_subject("CN=test1", "CN=test2") is False
    assert auth.validate_subject("CN=test,O=org", "CN=test") is False
    assert auth.validate_subject("", "CN=test") is False


def test_mtls_authentication_domain_components():
    """Test mTLS authentication with domain components."""
    auth = MTLSAuthentication(
        subject="DC=com,DC=example,CN=server",
        value="DC=com,DC=example,CN=server",
    )

    # Should not raise exception
    auth.authenticate()


def test_mtls_authentication_domain_components_order_independence():
    """Test mTLS authentication with domain components in different order."""
    auth = MTLSAuthentication(
        subject="CN=server,DC=example,DC=com",
        value="DC=com,DC=example,CN=server",
    )

    # Should not raise exception
    auth.authenticate()


def test_mtls_authentication_country_code_case_insensitive():
    """Test mTLS authentication with country code case differences."""
    auth = MTLSAuthentication(subject="CN=server,C=us", value="CN=server,C=US")

    # Should not raise exception
    auth.authenticate()


def test_mtls_authentication_organization_case_insensitive():
    """Test mTLS authentication with organization case differences."""
    auth = MTLSAuthentication(
        subject="CN=server,O=Test Organization",
        value="CN=server,O=test organization",
    )

    # Should not raise exception (organization names are case-insensitive)
    auth.authenticate()


def test_mtls_authentication_complex_dn_with_wildcards():
    """Test mTLS authentication with complex DN and wildcards."""
    subject = (
        "CN=.*\\.example\\.com,OU=IT Department,O=Company Inc,"
        "L=.*,ST=California,C=US"
    )
    value = (
        "CN=api.example.com,OU=IT Department,O=Company Inc,"
        "L=San Francisco,ST=California,C=US"
    )
    auth = MTLSAuthentication(subject=subject, value=value)

    # Should not raise exception
    auth.authenticate()


def test_mtls_authentication_edge_case_special_characters():
    """Test mTLS authentication with valid special characters in DN."""
    auth = MTLSAuthentication(
        subject="CN=test-server.example.com,O=Test Co",
        value="CN=test-server.example.com,O=Test Co",
    )

    # Should not raise exception
    auth.authenticate()


def test_mtls_authentication_performance_long_dn():
    """Test mTLS authentication with very long DN strings."""
    long_subject = (
        "CN=very-long-hostname-that-exceeds-normal-length.example.com,"
        "OU=Very Long Organizational Unit Name That Contains Many Words,"
        "O=Very Long Organization Name Incorporated With Extra Words,"
        "L=Very Long City Name With Multiple Words,"
        "ST=Very Long State Or Province Name,C=US"
    )

    auth = MTLSAuthentication(subject=long_subject, value=long_subject)

    # Should not raise exception and should complete quickly
    auth.authenticate()
