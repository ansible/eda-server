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
from unittest import mock

import pytest
from django.core.management import call_command
from django.test import override_settings


@pytest.mark.parametrize(
    "analytics_url, tracking_state, expected",
    [
        (None, False, "Insights for Event Driven Ansible is not enabled."),
        (
            "https://url",
            False,
            "No analytics collected",
        ),
        (None, True, "AUTOMATION_ANALYTICS_URL is not set"),
    ],
)
@pytest.mark.django_db
@override_settings(
    FLAGS={"FEATURE_EDA_ANALYTICS_ENABLED": [("boolean", True)]}
)
def test_gather_analytics_invalid_settings(
    analytics_settings,
    caplog_factory,
    analytics_url,
    tracking_state,
    expected,
):
    with mock.patch(
        "aap_eda.analytics.package.application_settings",
        new=analytics_settings,
    ):
        with mock.patch(
            "aap_eda.analytics.collector.application_settings",
            new=analytics_settings,
        ):
            analytics_settings.AUTOMATION_ANALYTICS_URL = analytics_url
            analytics_settings.INSIGHTS_TRACKING_STATE = tracking_state

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
@override_settings(
    FLAGS={"FEATURE_EDA_ANALYTICS_ENABLED": [("boolean", True)]}
)
@mock.patch(
    "aap_eda.core.management.commands.gather_analytics.collector.gather"
)
def test_gather_analytics_command(
    mock_gather, analytics_settings, caplog_factory, args, log_level, expected
):
    with mock.patch(
        "aap_eda.analytics.collector.application_settings",
        new=analytics_settings,
    ):
        with mock.patch(
            "aap_eda.analytics.package.application_settings",
            new=analytics_settings,
        ):
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
        (False, "FEATURE_EDA_ANALYTICS_ENABLED is set to False."),
    ],
)
def test_gather_analytics_command_by_ff_state(
    analytics_settings, caplog_factory, feature_flag_state, expected
):
    with mock.patch(
        "aap_eda.analytics.collector.application_settings",
        new=analytics_settings,
    ):
        analytics_settings.INSIGHTS_TRACKING_STATE = True
        out = StringIO()
        logger = logging.getLogger("aap_eda.analytics")
        eda_log = caplog_factory(logger)
        with override_settings(
            FLAGS={
                "FEATURE_EDA_ANALYTICS_ENABLED": [
                    ("boolean", feature_flag_state)
                ]
            }
        ):
            command = "gather_analytics"
            call_command(command, stdout=out)

        assert any(
            record.levelname == "ERROR" and record.message == expected
            for record in eda_log.records
        )
