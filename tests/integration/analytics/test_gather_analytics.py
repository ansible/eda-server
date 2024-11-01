#  Copyright 2024 Red Hat, Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import logging
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import override_settings

from aap_eda.conf import settings_registry
from aap_eda.conf.settings import application_settings


@pytest.fixture(autouse=True)
def register() -> None:
    settings_registry.persist_registry_data()
    return None


@pytest.fixture(autouse=True)
def use_analytic_url(settings):
    settings.AUTOMATION_ANALYTICS_URL = "https://analytics_url"


@pytest.mark.parametrize(
    "analytics_url, tracking_state, expected",
    [
        (None, False, "Insights for Event Driven Ansible is not enabled."),
        (
            "https://url",
            False,
            "Insights for Event Driven Ansible is not enabled.",
        ),
        (None, True, "AUTOMATION_ANALYTICS_URL is not set"),
        (
            "https://url",
            True,
            "Analytics collection is done",
        ),
    ],
)
@pytest.mark.django_db
@override_settings(FLAGS={"EDA_ANALYTICS": [("boolean", True)]})
def test_gather_analytics_invalid_settings(
    settings, caplog_factory, analytics_url, tracking_state, expected
):
    settings.AUTOMATION_ANALYTICS_URL = analytics_url
    application_settings.INSIGHTS_TRACKING_STATE = tracking_state

    out = StringIO()
    logger = logging.getLogger("aap_eda.analytics")
    eda_log = caplog_factory(logger)

    call_command("gather_analytics", "--ship", stdout=out)

    assert expected in eda_log.text


@pytest.mark.parametrize(
    "args, log_level, expected",
    [
        (None, "ERROR", "Either --ship or --dry-run needs to be set."),
        (
            "--ship",
            "INFO",
            "Analytics collection is done",
        ),
        (
            ("--ship", "--dry-run"),
            "ERROR",
            "Both --ship and --dry-run cannot be processed at the same time.",
        ),
        (
            ("--dry-run", "--since", "2024-08-20"),
            "INFO",
            "Analytics collection is done",
        ),
        (
            ("--dry-run", "--since", "'2024-08-20 19:44:43.622759+00'"),
            "INFO",
            "Analytics collection is done",
        ),
        (
            ("--dry-run", "--since", "'2024-08-20 19:44:43'"),
            "INFO",
            "Analytics collection is done",
        ),
        (
            ("--dry-run", "--since", "'2024-08-20 19:44:43.622759'"),
            "INFO",
            "Analytics collection is done",
        ),
        (
            ("--dry-run", "--until", "2024-09-20"),
            "INFO",
            "Analytics collection is done",
        ),
        (
            ("--dry-run", "--until", "'2024-09-20 19:44:43.622759+00'"),
            "INFO",
            "Analytics collection is done",
        ),
        (
            (
                "--dry-run",
                "--since",
                "'2024-08-20 19:44:43'",
                "--until",
                "'2024-09-20 19:44:43'",
            ),
            "INFO",
            "Analytics collection is done",
        ),
    ],
)
@pytest.mark.django_db
@override_settings(FLAGS={"EDA_ANALYTICS": [("boolean", True)]})
def test_gather_analytics_command(caplog_factory, args, log_level, expected):
    application_settings.INSIGHTS_TRACKING_STATE = True
    out = StringIO()
    logger = logging.getLogger("aap_eda.analytics")
    eda_log = caplog_factory(logger)

    command = "gather_analytics"
    if args:
        call_command(command, args, stdout=out)
    else:
        call_command(command, stdout=out)

    assert any(
        record.levelname == log_level and record.message == expected
        for record in eda_log.records
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "feature_flag_state, expected",
    [
        (True, "Either --ship or --dry-run needs to be set."),
        (False, "EDA_ANALYTICS is disabled."),
    ],
)
def test_gather_analytics_command_by_ff_state(
    caplog_factory, feature_flag_state, expected
):
    application_settings.INSIGHTS_TRACKING_STATE = True
    out = StringIO()
    logger = logging.getLogger("aap_eda.analytics")
    eda_log = caplog_factory(logger)
    if feature_flag_state:
        call_command("enable_flag", "EDA_ANALYTICS", stdout=out)

    command = "gather_analytics"
    call_command(command, stdout=out)

    assert any(
        record.levelname == "ERROR" and record.message == expected
        for record in eda_log.records
    )
