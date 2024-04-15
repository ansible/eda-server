import pytest
from django.conf import settings
from rest_framework.serializers import ValidationError

from aap_eda.core.validators import (
    check_if_rcf_1035_compliant,
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


def test_check_if_rcf_1035_compliant():
    settings.DEPLOYMENT_TYPE = "k8s"
    incompatible_name = "A-test-value"

    with pytest.raises(ValidationError):
        check_if_rcf_1035_compliant(incompatible_name)
