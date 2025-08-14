import pytest
from django.conf import settings
from rest_framework.serializers import ValidationError

from aap_eda.core.validators import (
    check_if_rfc_1035_compliant,
    check_if_scm_url_valid,
    check_rulesets_require_token,
)

RULEBOOK_WITH_JOB_TEMPLATE_MULTIPLE_ACTIONS = [
    {
        "name": "test",
        "sources": [],
        "rules": [
            {
                "name": "test",
                "condition": "true",
                "actions": [
                    {
                        "run_job_template": {},
                    },
                    {"debug": "test"},
                ],
            },
        ],
    },
]

RULEBOOK_WITHOUT_JOB_TEMPLATE_MULTIPLE_ACTIONS = [
    {
        "name": "test",
        "sources": [],
        "rules": [
            {
                "name": "test",
                "condition": "true",
                "actions": [
                    {
                        "debug": {},
                    },
                    {
                        "print_event": {},
                    },
                ],
            },
        ],
    },
]

RULEBOOK_WITH_WORKFLOW_TEMPLATE_MULTIPLE_ACTIONS = [
    {
        "name": "test",
        "sources": [],
        "rules": [
            {
                "name": "test",
                "condition": "true",
                "actions": [
                    {
                        "run_workflow_template": {},
                    },
                    {"debug": "test"},
                ],
            },
        ],
    },
]

RULEBOOK_WITH_WORKFLOW_TEMPLATE_SINGLE_ACTION = [
    {
        "name": "test",
        "sources": [],
        "rules": [
            {
                "name": "test",
                "condition": "true",
                "action": {
                    "run_workflow_template": {},
                },
            },
        ],
    },
]

RULEBOOK_WITHOUT_WORKFLOW_TEMPLATE_SINGLE_ACTION = [
    {
        "name": "test",
        "sources": [],
        "rules": [
            {
                "name": "test",
                "condition": "true",
                "action": {
                    "debug": {},
                },
            },
        ],
    },
]

RULEBOOK_WITH_JOB_TEMPLATE_MIXED_MULTIPLE_RULESETS = [
    {
        "name": "test",
        "sources": [],
        "rules": [
            {
                "name": "test",
                "condition": "true",
                "actions": [
                    {
                        "run_job_template": {},
                    },
                    {"debug": "test"},
                ],
            },
        ],
    },
    {
        "name": "test",
        "sources": [],
        "rules": [
            {
                "name": "test",
                "condition": "true",
                "action": {
                    "run_job_template": {},
                },
            },
        ],
    },
]

RULEBOOK_WITHOUT_JOB_TEMPLATE_MIXED_MULTIPLE_RULESETS = [
    {
        "name": "test",
        "sources": [],
        "rules": [
            {
                "name": "test",
                "condition": "true",
                "actions": [
                    {
                        "debug": {},
                    },
                    {
                        "print_event": {},
                    },
                ],
            },
        ],
    },
    {
        "name": "test",
        "sources": [],
        "rules": [
            {
                "name": "test",
                "condition": "true",
                "action": {
                    "debug": {},
                },
            },
        ],
    },
]


@pytest.mark.parametrize(
    "rulesets_data, expected",
    [
        (RULEBOOK_WITH_JOB_TEMPLATE_MULTIPLE_ACTIONS, True),
        (RULEBOOK_WITHOUT_JOB_TEMPLATE_MULTIPLE_ACTIONS, False),
        (RULEBOOK_WITH_WORKFLOW_TEMPLATE_MULTIPLE_ACTIONS, True),
        (RULEBOOK_WITH_WORKFLOW_TEMPLATE_SINGLE_ACTION, True),
        (RULEBOOK_WITHOUT_WORKFLOW_TEMPLATE_SINGLE_ACTION, False),
        (RULEBOOK_WITH_JOB_TEMPLATE_MIXED_MULTIPLE_RULESETS, True),
        (RULEBOOK_WITHOUT_JOB_TEMPLATE_MIXED_MULTIPLE_RULESETS, False),
    ],
)
def test_check_rulesets_require_token(rulesets_data, expected):
    assert check_rulesets_require_token(rulesets_data) == expected


def test_check_if_rfc_1035_compliant():
    settings.DEPLOYMENT_TYPE = "k8s"
    incompatible_name = "A-test-value"

    with pytest.raises(ValidationError):
        check_if_rfc_1035_compliant(incompatible_name)


@pytest.mark.parametrize(
    "url,expected",
    [
        # Basic valid URLs
        ("git@git.ex-ample.com:user/repo.git", True),
        ("http://git.example.com/repo.git/sub/r2.git", True),  # /NOSONAR
        ("https://git.example.com/repo", True),
        ("ssh://git.example.com/repo.git/", True),
        ("git://git.example.com/repo.git", True),
        ("git+ssh://git.example.com/repo.git", True),
        # URLs with authentication
        ("https://user:pass@git.example.com/repo.git", True),
        ("https://token@git.example.com/repo.git", True),
        ("git+ssh://user@git.example.com/repo.git", True),
        # URLs with ports
        ("https://git.example.com:8080/repo.git", True),
        ("ssh://git.example.com:22/repo.git", True),
        ("git://git.example.com:9418/repo.git", True),
        # URLs with URL encoding
        ("https://git.example.com/user/repo%20with%20spaces.git", True),
        ("https://git.example.com/user/repo%2Dwith%2Ddashes.git", True),
        ("git@git.example.com:user/repo%20name.git", True),
        # IPv6 hosts
        ("https://[2001:db8::1]/repo.git", True),
        ("https://[::1]:8080/repo.git", True),
        ("git://[2001:db8::1]/repo.git", True),
        ("ssh://[::1]/repo.git", True),
        ("git@[2001:db8::1]:repo.git", True),  # SSH with IPv6
        ("git@[::1]:user/repo.git", True),  # SSH with localhost IPv6
        # URLs with query parameters
        ("https://git.example.com/repo.git?ref=main", True),
        ("https://git.example.com/repo.git?shallow=1&depth=50", True),
        ("git://git.example.com/repo.git?service=git-upload-pack", True),
        # URLs with fragments
        ("https://git.example.com/repo.git#main", True),
        ("https://git.example.com/repo.git#feature/branch", True),
        # Edge cases that should be valid
        ("https://git.example.com/repo", True),  # No .git extension
        ("https://git.example.com/user/repo.git/", True),  # Trailing slash
        ("git@git-server.internal:group/subgroup/project.git", True),
        ("https://git.example.com/very/deep/nested/path/repo.git", True),
        # Invalid URLs - Bad characters
        ("ssh://git.example.com/re^po.git", False),
        ("https://git.example.com/repo|pipe.git", False),
        ("git@git.example.com:user/repo{{lookup}}.git", False),
        ("https://git.example.com/repo}close.git", False),
        # Invalid URLs - Malformed
        ("", False),  # Empty string
        ("not-a-url", False),
        ("ftp://git.example.com/repo.git", False),  # Unsupported scheme
        ("https://", False),  # Missing hostname
        ("https:///host/path", False),  # Three slashes - malformed
        ("https://git.example.com", False),  # Missing path
        ("git@", False),  # Incomplete SSH format
        ("git@host", False),  # Missing colon and path in SSH format
        ("git@2001:db8::1:repo.git", False),  # IPv6 without brackets in SSH
        ("://git.example.com/repo.git", False),  # Missing scheme
        # Invalid URLs - Bad hostnames
        ("https://..invalid../repo.git", False),
        ("https://host..double.dot/repo.git", False),
        ("ssh://bad host with spaces/repo.git", False),
        # Invalid IPv6
        ("https://[invalid:ipv6]/repo.git", False),
        (
            "https://[2001:db8::1:8080/repo.git",
            False,
        ),  # Missing closing bracket
        ("git@[invalid:ipv6]:repo.git", False),  # Invalid chars in SSH IPv6
        ("git@[2001:db8::1:8080/repo.git", False),  # Missing bracket in SSH
        ("git@[]:repo.git", False),  # Empty brackets in SSH
        # URLs that might be used for injection attempts
        ("https://git.example.com/repo.git; rm -rf /", False),
        ("git@git.example.com:user/repo.git && malicious", False),
        ("https://git.example.com/repo.git`command`", False),
        ("git@host:repo with space.git", False),
    ],
)
def test_check_if_scm_url_valid(url: str, expected: bool):
    if expected:
        # Should not raise an exception and return the URL
        result = check_if_scm_url_valid(url)
        assert result == url
    else:
        # Should raise a ValidationError
        with pytest.raises(ValidationError) as exc_info:
            check_if_scm_url_valid(url)
        assert "Invalid source control URL:" in str(exc_info.value)
