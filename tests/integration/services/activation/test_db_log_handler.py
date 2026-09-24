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
from aap_eda.services.activation.db_log_handler import (
    LOG_RETENTION_CHECK_INTERVAL,
    DBLogger,
)


@pytest.mark.django_db
def test_enforce_max_log_lines_trims_oldest(default_activation_instance):
    """Oldest rows are deleted when count exceeds cap."""
    with patch("django.conf.settings.MAX_LOG_LINES_PER_INSTANCE", 5):
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
    default_activation_instance.refresh_from_db()
    assert default_activation_instance.stored_lines_since_cap_check == 0


@pytest.mark.django_db
def test_enforce_max_log_lines_disabled_when_zero(
    default_activation_instance,
):
    """Setting=0 means no cap; all lines are kept."""
    with patch("django.conf.settings.MAX_LOG_LINES_PER_INSTANCE", 0):
        with patch.object(DBLogger, "_enforce_max_log_lines") as enforce:
            obj = DBLogger(default_activation_instance.id)
            for i in range(1000):
                obj.write(f"line-{i}")
            obj.flush()
            enforce.assert_not_called()

    count = RulebookProcessLog.objects.filter(
        activation_instance=default_activation_instance,
    ).count()
    assert count == 1000
    default_activation_instance.refresh_from_db()
    assert default_activation_instance.stored_lines_since_cap_check == 0


@pytest.mark.django_db
def test_retention_checkpoint_waits_for_1000_stored_lines(
    default_activation_instance,
):
    """The cap check waits for 1,000 stored rows across logger instances."""
    with patch("django.conf.settings.MAX_LOG_LINES_PER_INSTANCE", 5):
        for start, count in ((0, 499), (499, 500)):
            obj = DBLogger(default_activation_instance.id)
            obj.write([f"line-{i:04d}" for i in range(start, start + count)])
            obj.flush()

    log_query = RulebookProcessLog.objects.filter(
        activation_instance=default_activation_instance,
    )
    assert log_query.count() == 999
    assert log_query.count() <= 5 + LOG_RETENTION_CHECK_INTERVAL - 1
    default_activation_instance.refresh_from_db()
    assert default_activation_instance.stored_lines_since_cap_check == 999

    with patch("django.conf.settings.MAX_LOG_LINES_PER_INSTANCE", 5):
        obj = DBLogger(default_activation_instance.id)
        obj.write("line-0999")
        obj.flush()

    logs = list(log_query.order_by("id").values_list("log", flat=True))
    assert len(logs) == 5
    assert logs == [f"line-{i:04d}" for i in range(995, 1000)]
    default_activation_instance.refresh_from_db()
    assert default_activation_instance.stored_lines_since_cap_check == 0


@pytest.mark.django_db
def test_large_batch_enforces_and_preserves_checkpoint_remainder(
    default_activation_instance,
):
    """A large batch enforces once and retains its checkpoint remainder."""
    with patch("django.conf.settings.MAX_LOG_LINES_PER_INSTANCE", 10):
        obj1 = DBLogger(default_activation_instance.id)
        obj1.write(
            [f"line-{i:04d}" for i in range(LOG_RETENTION_CHECK_INTERVAL + 5)]
        )
        obj1.flush()

        default_activation_instance.refresh_from_db()
        assert default_activation_instance.stored_lines_since_cap_check == 5
        assert obj1.num_of_log_lines() == 10

        obj2 = DBLogger(default_activation_instance.id)
        obj2.write([f"next-{i:04d}" for i in range(994)])
        obj2.flush()

        default_activation_instance.refresh_from_db()
        assert default_activation_instance.stored_lines_since_cap_check == 999
        assert obj2.num_of_log_lines() == 1004

        obj3 = DBLogger(default_activation_instance.id)
        obj3.write("next-0994")
        obj3.flush()

        default_activation_instance.refresh_from_db()
        assert default_activation_instance.stored_lines_since_cap_check == 0
        assert obj3.num_of_log_lines() == 10

        logs = list(
            RulebookProcessLog.objects.filter(
                activation_instance=default_activation_instance,
            )
            .order_by("id")
            .values_list("log", flat=True)
        )
        assert logs == [f"next-{i:04d}" for i in range(985, 995)]


@pytest.mark.django_db
def test_filtered_debug_lines_do_not_advance_checkpoint(
    default_activation_instance,
):
    """Rows filtered from DB persistence do not trigger retention checks."""
    with patch("django.conf.settings.MAX_LOG_LINES_PER_INSTANCE", 5):
        with patch.object(DBLogger, "num_of_log_lines") as count:
            obj = DBLogger(default_activation_instance.id)
            obj.write(
                [
                    f"DEBUG hidden-{i}"
                    for i in range(LOG_RETENTION_CHECK_INTERVAL)
                ]
            )
            obj.flush()
            count.assert_not_called()

    assert not RulebookProcessLog.objects.filter(
        activation_instance=default_activation_instance,
    ).exists()
    default_activation_instance.refresh_from_db()
    assert default_activation_instance.stored_lines_since_cap_check == 0


@pytest.mark.django_db
def test_empty_flush_does_not_count_for_retention(default_activation_instance):
    """An empty flush does not invoke the exact retention count."""
    with patch.object(DBLogger, "num_of_log_lines") as count:
        DBLogger(default_activation_instance.id).flush()

    count.assert_not_called()
