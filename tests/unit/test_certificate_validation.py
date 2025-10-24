"""Unit tests for certificate validation functionality."""
from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from aap_eda.core.utils.credentials import (
    _normalize_x509_dn_whitespace,
    _validate_certificate_subject_format,
    _validate_pem_certificate,
    validate_x509_subject_match,
)


@pytest.mark.parametrize(
    "cert_data,expected_error",
    [
        ("", "Certificate data cannot be empty"),
        ("not a certificate", "Invalid PEM certificate format"),
        (
            "-----BEGIN CERTIFICATE-----\ninvalid\n-----END CERTIFICATE-----",
            "Invalid PEM certificate format",
        ),
    ],
)
def test_invalid_certificate_validation(cert_data, expected_error):
    """Test validation of invalid certificate data."""
    errors = _validate_pem_certificate(cert_data)
    assert len(errors) >= 1
    assert (
        expected_error in errors[0]
        or "No valid certificates found" in errors[0]
    )


def test_valid_certificate_validation():
    """Test validation of valid certificate."""
    # Generate a test certificate
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Testing"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Local"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test Org"),
            x509.NameAttribute(NameOID.COMMON_NAME, "test.example.com"),
        ]
    )

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
        .sign(private_key, hashes.SHA256())
    )

    # Convert to PEM
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")

    # Should validate successfully
    errors = _validate_pem_certificate(cert_pem)
    assert len(errors) == 0


def test_expired_certificate_validation():
    """Test validation of expired certificate."""
    # Generate an expired test certificate
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "expired.example.com"),
        ]
    )

    # Create certificate that expired yesterday
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    two_days_ago = yesterday - timedelta(days=1)

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(two_days_ago)
        .not_valid_after(yesterday)
        .sign(private_key, hashes.SHA256())
    )

    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")

    errors = _validate_pem_certificate(cert_pem)
    assert len(errors) == 1
    assert "Certificate has expired" in errors[0]


@pytest.mark.parametrize(
    "subject",
    [
        "",  # Empty is allowed
        "CN=example.com",
        (
            "CN=server.example.com,OU=IT Department,O=Company Inc,"
            "L=City,ST=State,C=US"
        ),
        "CN=test,C=US",
        "DC=com,DC=example,CN=server",
        "  CN = example.com  ,  O = Test Org  ",  # Whitespace handling
    ],
)
def test_subject_format_validation_valid(subject):
    """Test validation of valid subject formats."""
    errors = _validate_certificate_subject_format(subject)
    assert len(errors) == 0


@pytest.mark.parametrize(
    "subject,expected_error",
    [
        ("INVALID=value", "Invalid X.509 DN format"),
        ("CN test", "Invalid X.509 DN format"),
        ("=value", "Invalid X.509 DN format"),
        ("CN=Acme,Inc", "Invalid X.509 DN format"),
        ("CN=test1,CN=test2", "Duplicate attributes not allowed"),
        ("CN=test,C=USA", "Country name must be a 2 character country code"),
    ],
)
def test_subject_format_validation_invalid(subject, expected_error):
    """Test validation of invalid subject formats."""
    errors = _validate_certificate_subject_format(subject)
    assert len(errors) >= 1
    assert expected_error in errors[0]


def test_subject_format_validation_mixed_case_attributes():
    """Test subject format validation with mixed case attributes."""
    # Mixed case should now be handled by X.509 standard parsing
    errors = _validate_certificate_subject_format("CN=test,O=org")
    assert len(errors) == 0  # Should be valid with X.509 parsing


def test_subject_format_validation_exception_handling():
    """Test subject format validation exception handling."""
    # This will test the except block in _validate_certificate_subject_format
    # by providing a case that could cause an exception during parsing
    errors = _validate_certificate_subject_format("CN=test,=")
    assert len(errors) >= 1
    # Should contain parsing error


# New tests for X.509 subject matching functionality


def test_normalize_x509_dn_whitespace():
    """Test _normalize_x509_dn_whitespace function."""
    # Test basic whitespace normalization
    result = _normalize_x509_dn_whitespace(
        "  CN = example.com  ,  O = Test Org  "
    )
    assert result == "CN=example.com,O=Test Org"

    # Test empty string
    result = _normalize_x509_dn_whitespace("")
    assert result == ""

    # Test component without equals
    result = _normalize_x509_dn_whitespace("CN=test,  invalid  ")
    assert result == "CN=test,invalid"

    # Test multiple components
    result = _normalize_x509_dn_whitespace("CN=test,O=org,C=US")
    assert result == "CN=test,O=org,C=US"


def test_validate_x509_subject_match_exact():
    """Test validate_x509_subject_match with exact matching."""
    # Exact match
    assert (
        validate_x509_subject_match("CN=example.com", "CN=example.com") is True
    )

    # Case insensitive for most attributes
    assert (
        validate_x509_subject_match("CN=Example.com", "CN=example.com") is True
    )

    # Order independence
    assert (
        validate_x509_subject_match("CN=test,O=org", "O=org,CN=test") is True
    )

    # Whitespace normalization
    assert (
        validate_x509_subject_match("CN=test, O=org", "CN=test,O=org") is True
    )

    # Missing attribute in actual
    assert validate_x509_subject_match("CN=test,O=org", "CN=test") is False

    # Different values
    assert validate_x509_subject_match("CN=test1", "CN=test2") is False

    # Empty/None inputs
    assert validate_x509_subject_match("", "CN=test") is False
    assert validate_x509_subject_match("CN=test", "") is False
    assert validate_x509_subject_match("", "") is False


def test_validate_x509_subject_match_wildcards():
    """Test validate_x509_subject_match with regex wildcard patterns."""
    # Basic wildcard (using .* regex pattern)
    assert (
        validate_x509_subject_match(
            "CN=.*\\.example\\.com", "CN=server.example.com"
        )
        is True
    )
    assert (
        validate_x509_subject_match(
            "CN=.*\\.example\\.com", "CN=api.example.com"
        )
        is True
    )
    assert (
        validate_x509_subject_match(
            "CN=.*\\.example\\.com", "CN=other.domain.com"
        )
        is False
    )

    # Multiple wildcards
    assert (
        validate_x509_subject_match("CN=.*\\..*", "CN=server.example.com")
        is True
    )
    assert (
        validate_x509_subject_match(
            "CN=.*\\.example\\.com,O=R.*",
            "O=R&D Development,CN=server.example.com",
        )
        is True
    )

    # Wildcard with other attributes
    assert (
        validate_x509_subject_match(
            "CN=.*\\.example\\.com,O=Test", "CN=server.example.com,O=Test"
        )
        is True
    )
    assert (
        validate_x509_subject_match(
            "CN=(agent1|agent2)\\.example\\.com", "CN=agent1.example.com"
        )
        is True
    )

    # Wildcard mismatch
    assert (
        validate_x509_subject_match(
            "CN=.*\\.example\\.com,O=Test", "CN=server.example.com,O=Other"
        )
        is False
    )
    assert (
        validate_x509_subject_match(
            "CN=.*\\.example\\.com,O=Test", "CN=server.agent.com,O=Test"
        )
        is False
    )


def test_validate_x509_subject_match_country_codes():
    """Test validate_x509_subject_match with country code handling."""
    # Country codes should be case insensitive
    assert validate_x509_subject_match("C=us", "C=US") is True
    assert validate_x509_subject_match("C=US", "C=us") is True

    # With other attributes
    assert validate_x509_subject_match("CN=test,C=us", "CN=test,C=US") is True


def test_validate_x509_subject_match_domain_components():
    """Test validate_x509_subject_match with domain components."""
    # Multiple DC attributes should work
    assert (
        validate_x509_subject_match(
            "DC=com,DC=example,CN=server", "DC=com,DC=example,CN=server"
        )
        is True
    )

    # Order should not matter for DC
    assert (
        validate_x509_subject_match(
            "CN=server,DC=example,DC=com", "DC=com,DC=example,CN=server"
        )
        is True
    )


def test_validate_x509_subject_match_invalid_dn():
    """Test validate_x509_subject_match with invalid DN strings."""
    # Invalid DN format should return False
    assert validate_x509_subject_match("INVALID=test", "CN=test") is False
    assert validate_x509_subject_match("CN=test", "INVALID=test") is False

    # Malformed DN
    assert validate_x509_subject_match("CN test", "CN=test") is False


def test_validate_x509_subject_match_edge_cases():
    """Test validate_x509_subject_match edge cases."""
    # Test with special characters that need escaping in regex
    assert (
        validate_x509_subject_match(
            "CN=test.example.com", "CN=test.example.com"
        )
        is True
    )

    # Test with valid DN special characters
    assert (
        validate_x509_subject_match(
            "CN=test-server.example.com", "CN=test-server.example.com"
        )
        is True
    )

    # Test very long DN strings
    long_dn = (
        "CN=very-long-hostname-that-exceeds-normal-length.example.com,"
        "OU=Very Long Organizational Unit Name,"
        "O=Very Long Organization Name Inc,"
        "L=Very Long City Name,ST=Very Long State Name,C=US"
    )
    assert validate_x509_subject_match(long_dn, long_dn) is True


# New tests for regex pattern matching functionality


def test_validate_x509_subject_match_regex_patterns():
    """Test validate_x509_subject_match with regex patterns."""
    # Character class patterns
    assert (
        validate_x509_subject_match(
            "CN=agent[1-9]\\.example\\.com", "CN=agent5.example.com"
        )
        is True
    )
    assert (
        validate_x509_subject_match(
            "CN=agent[1-9]\\.example\\.com", "CN=agent0.example.com"
        )
        is False
    )
    assert (
        validate_x509_subject_match(
            "CN=server[a-z]\\.domain\\.com", "CN=serverx.domain.com"
        )
        is True
    )

    # Alternation patterns
    assert (
        validate_x509_subject_match(
            "CN=(agent1|agent2)\\.example\\.com", "CN=agent1.example.com"
        )
        is True
    )
    assert (
        validate_x509_subject_match(
            "CN=(agent1|agent2)\\.example\\.com", "CN=agent2.example.com"
        )
        is True
    )
    assert (
        validate_x509_subject_match(
            "CN=(agent1|agent2)\\.example\\.com", "CN=agent3.example.com"
        )
        is False
    )

    # Plus quantifier patterns
    assert (
        validate_x509_subject_match(
            "CN=server-[0-9]+\\.domain\\.com", "CN=server-123.domain.com"
        )
        is True
    )
    assert (
        validate_x509_subject_match(
            "CN=server-[0-9]+\\.domain\\.com", "CN=server-1.domain.com"
        )
        is True
    )
    assert (
        validate_x509_subject_match(
            "CN=server-[0-9]+\\.domain\\.com", "CN=server-.domain.com"
        )
        is False
    )

    # Dot wildcard patterns
    assert (
        validate_x509_subject_match(
            "CN=.*\\.example\\.com", "CN=anything.example.com"
        )
        is True
    )
    assert (
        validate_x509_subject_match(
            "CN=.*\\.example\\.com", "CN=multi.part.example.com"
        )
        is True
    )
    assert (
        validate_x509_subject_match(
            "CN=.*\\.example\\.com", "CN=test.other.com"
        )
        is False
    )


def test_validate_x509_subject_match_regex_complex_patterns():
    """Test validate_x509_subject_match with complex regex patterns."""
    # Mixed patterns with multiple attributes
    assert (
        validate_x509_subject_match(
            "CN=app[1-3]\\.example\\.com,O=(Dev|Test|Prod)",
            "CN=app2.example.com,O=Dev",
        )
        is True
    )
    assert (
        validate_x509_subject_match(
            "CN=app[1-3]\\.example\\.com,O=(Dev|Test|Prod)",
            "CN=app2.example.com,O=Staging",
        )
        is False
    )

    # Optional groups
    assert (
        validate_x509_subject_match(
            "CN=server(-[0-9]+)?\\.domain\\.com", "CN=server.domain.com"
        )
        is True
    )
    assert (
        validate_x509_subject_match(
            "CN=server(-[0-9]+)?\\.domain\\.com", "CN=server-123.domain.com"
        )
        is True
    )

    # Word boundaries
    assert (
        validate_x509_subject_match(
            "CN=\\btest\\b\\.example\\.com", "CN=test.example.com"
        )
        is True
    )
    assert (
        validate_x509_subject_match(
            "CN=\\btest\\b\\.example\\.com", "CN=testing.example.com"
        )
        is False
    )

    # Case sensitivity with regex
    assert (
        validate_x509_subject_match(
            "CN=SERVER[0-9]\\.DOMAIN\\.COM", "CN=server5.domain.com"
        )
        is True
    )


def test_validate_x509_subject_match_regex_special_characters():
    """Test validate_x509_subject_match with special regex characters."""
    # Escaped special characters
    assert (
        validate_x509_subject_match(
            "CN=test\\$server\\.example\\.com", "CN=test$server.example.com"
        )
        is True
    )
    assert (
        validate_x509_subject_match(
            "CN=server-api\\.example\\.com", "CN=server-api.example.com"
        )
        is True
    )
    assert (
        validate_x509_subject_match(
            "CN=app\\(v2\\)\\.example\\.com", "CN=app(v2).example.com"
        )
        is True
    )

    # Brackets in actual certificate subject (literal matching)
    assert (
        validate_x509_subject_match(
            "CN=\\[agent1\\|agent2\\]\\.example\\.com",
            "CN=[agent1|agent2].example.com",
        )
        is True
    )

    # Character classes with special chars
    assert (
        validate_x509_subject_match(
            "CN=test[._-]server\\.com", "CN=test.server.com"
        )
        is True
    )
    assert (
        validate_x509_subject_match(
            "CN=test[._-]server\\.com", "CN=test_server.com"
        )
        is True
    )
    assert (
        validate_x509_subject_match(
            "CN=test[._-]server\\.com", "CN=test-server.com"
        )
        is True
    )


def test_validate_x509_subject_match_regex_anchoring():
    """Test that regex patterns are properly anchored."""
    # Should not match substring
    assert (
        validate_x509_subject_match("CN=server", "CN=test-server.example.com")
        is False
    )

    # Should match full string
    assert (
        validate_x509_subject_match(
            "CN=.*server.*", "CN=test-server.example.com"
        )
        is True
    )

    # Ensure anchoring works with complex patterns
    assert (
        validate_x509_subject_match("CN=server[0-9]", "CN=myserver5.com")
        is False
    )


@pytest.mark.parametrize(
    "pattern,subject,expected",
    [
        # Basic regex patterns
        ("CN=server[0-9]\\.com", "CN=server5.com", True),
        ("CN=server[0-9]\\.com", "CN=serverX.com", False),
        ("CN=(dev|prod)\\.example\\.com", "CN=dev.example.com", True),
        ("CN=(dev|prod)\\.example\\.com", "CN=test.example.com", False),
        # Quantifiers
        ("CN=app[0-9]+\\.domain\\.com", "CN=app123.domain.com", True),
        ("CN=app[0-9]+\\.domain\\.com", "CN=app.domain.com", False),
        ("CN=test[a-z]?\\.com", "CN=test.com", True),
        ("CN=test[a-z]?\\.com", "CN=testa.com", True),
        # Complex patterns
        ("CN=.*-v[0-9]+\\.example\\.com", "CN=api-v2.example.com", True),
        ("CN=.*-v[0-9]+\\.example\\.com", "CN=api-v.example.com", False),
        ("CN=\\w+\\.internal\\.com", "CN=service123.internal.com", True),
        ("CN=\\w+\\.internal\\.com", "CN=service-123.internal.com", False),
        # Multi-attribute patterns
        ("CN=app[1-3]\\.com,O=Test.*", "CN=app2.com,O=Test Org", True),
        ("CN=app[1-3]\\.com,O=Test.*", "CN=app2.com,O=Prod Org", False),
        # Case insensitivity
        ("CN=SERVER[0-9]\\.COM", "CN=server5.com", True),
        ("CN=server[0-9]\\.com", "CN=SERVER5.COM", True),
        # Special characters
        ("CN=test\\$[0-9]\\.com", "CN=test$5.com", True),
        ("CN=test-api\\.com", "CN=test-api.com", True),
        ("CN=\\[prod\\]\\.com", "CN=[prod].com", True),
    ],
)
def test_validate_x509_subject_match_regex_parametrized(
    pattern, subject, expected
):
    """Parametrized test for various regex patterns."""
    result = validate_x509_subject_match(pattern, subject)
    assert result is expected


def test_validate_x509_subject_match_performance_edge_cases():
    """Test performance and edge cases with regex patterns."""
    # Very long patterns
    long_pattern = "CN=" + "a" * 1000 + "[0-9]\\.com"
    long_subject = "CN=" + "a" * 1000 + "5.com"
    assert validate_x509_subject_match(long_pattern, long_subject) is True

    # Pattern with many alternations
    many_alt_pattern = (
        "CN=(" + "|".join([f"server{i}" for i in range(100)]) + ")\\.com"
    )
    assert (
        validate_x509_subject_match(many_alt_pattern, "CN=server50.com")
        is True
    )
    assert (
        validate_x509_subject_match(many_alt_pattern, "CN=server999.com")
        is False
    )

    # Empty regex groups
    assert (
        validate_x509_subject_match("CN=test()\\.com", "CN=test.com") is True
    )
