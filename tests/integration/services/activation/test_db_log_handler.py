#  Copyright 2025 Red Hat, Inc.
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

from unittest.mock import patch

import pytest

from aap_eda.core.models.rulebook_process import RulebookProcessLog
from aap_eda.services.activation.db_log_handler import DBLogger


@pytest.mark.django_db
def test_enforce_max_log_lines_trims_oldest(default_activation_instance):
    """Oldest rows are deleted when count exceeds cap."""
    with patch("django.conf.settings.EDA_MAX_LOG_LINES_PER_INSTANCE", 5):
        obj = DBLogger(default_activation_instance.id)
        for i in range(1000):
            obj.write(f"line-{i:04d}")  # noqa: E231
        obj.flush()

    logs = list(
        RulebookProcessLog.objects.filter(
            activation_instance=default_activation_instance,
        )
        .order_by("id")
        .values_list("log", flat=True)
    )
    assert len(logs) == 5
    assert logs[0] == "line-0995"
    assert logs[-1] == "line-0999"


@pytest.mark.django_db
def test_enforce_max_log_lines_disabled_when_zero(
    default_activation_instance,
):
    """Setting=0 means no cap; all lines are kept."""
    with patch("django.conf.settings.EDA_MAX_LOG_LINES_PER_INSTANCE", 0):
        obj = DBLogger(default_activation_instance.id)
        for i in range(1000):
            obj.write(f"line-{i}")
        obj.flush()

    count = RulebookProcessLog.objects.filter(
        activation_instance=default_activation_instance,
    ).count()
    assert count == 1000


@pytest.mark.django_db
def test_enforce_max_log_lines_check_interval(default_activation_instance):
    """COUNT only runs at 1000-line intervals."""
    with patch("django.conf.settings.EDA_MAX_LOG_LINES_PER_INSTANCE", 5):
        obj = DBLogger(default_activation_instance.id)
        for i in range(999):
            obj.write(f"line-{i}")
        obj.flush()

    count = RulebookProcessLog.objects.filter(
        activation_instance=default_activation_instance,
    ).count()
    assert count == 999
