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

from datetime import datetime
from importlib import import_module
from typing import Type
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.models import Model
from django.utils.timezone import make_aware

from aap_eda.core import models

TEST_DATA = [
    {
        "msg": "2025-01-17 18:39:49,191 Starting Container",
        "dt": make_aware(datetime(2025, 1, 17, 18, 39, 49, 191000)),
        "log": "Starting Container",
    },
    {
        "msg": "** 2025-01-17 18:39:55.222773 [debug] ****",
        "dt": make_aware(datetime(2025, 1, 17, 18, 39, 55, 222773)),
        "log": "[debug] ****",
    },
    {
        "msg": "2025-01-17 18:43:38 638 [main] DEBUG org.drools.ansible",
        "dt": make_aware(datetime(2025, 1, 17, 18, 43, 38, 638000)),
        "log": "[main] DEBUG org.drools.ansible",
    },
    {
        "msg": "[main] DEBUG org.drools.ansible",
        "dt": None,
        "log": "[main] DEBUG org.drools.ansible",
    },
    {
        "msg": "2025-01-17T18:43:38.222773Z [main] DEBUG org.drools.ansible",
        "dt": None,
        "log": "2025-01-17T18:43:38.222773Z [main] DEBUG org.drools.ansible",
    },
]


def get_historical_model(
    app_label: str, model_name: str, migration_name: str
) -> Type[Model]:
    """
    Retrieves the historical model as it existed at the specified migration.
    """
    executor = MigrationExecutor(connection)

    # Load the migration state at the specified migration
    state = executor.loader.project_state((app_label, migration_name))

    return state.apps.get_model(app_label, model_name)


@pytest.fixture
def historical_rulebook_process_logs(
    default_activation_instance: models.RulebookProcess,
) -> list[models.RulebookProcessLog]:
    # get historical model
    historical_rulebook_process_log_model = get_historical_model(
        "core",
        "RulebookProcessLog",
        "0055_activation_created_by_activation_modified_by_and_more",
    )

    """Return a list of rulebook process logs."""
    return historical_rulebook_process_log_model.objects.bulk_create(
        historical_rulebook_process_log_model(
            log=data["msg"],
            activation_instance_id=default_activation_instance.id,
        )
        for data in TEST_DATA
    )


@pytest.fixture
def reset_migrations():
    call_command("migrate", "core", "0055")
    yield
    call_command("migrate")


@pytest.mark.django_db(transaction=True)
def test_migration(historical_rulebook_process_logs, reset_migrations):
    for log in historical_rulebook_process_logs:
        assert not hasattr(log, "log_created_at")

    call_command("migrate", "core", "0056")

    for i, log in enumerate(models.RulebookProcessLog.objects.all()):
        log.refresh_from_db()
        assert log.log_created_at == TEST_DATA[i]["dt"]
        assert log.log == TEST_DATA[i]["log"]


@pytest.mark.django_db
def test_up_log_entries_chunk_size():
    migration_module = import_module(
        "aap_eda.core.migrations.0056_rulebookprocesslog_log_created_at_and_more"  # noqa E501
    )

    mock_apps = MagicMock()
    mock_model = MagicMock()
    mock_apps.get_model.return_value = mock_model

    chunk_size = migration_module.CHUNK_SIZE
    mock_entries = [
        MagicMock(id=i, log=f"log {i}") for i in range(chunk_size * 2 + 1)
    ]
    mock_model.objects.iterator.return_value = mock_entries

    with patch.object(
        migration_module,
        "extract_datetime_and_message_from_log_entry",
        side_effect=lambda log: ("2025-01-27 00:00:00", f"parsed {log}"),
    ) as mock_extract:
        with patch.object(migration_module, "logger") as mock_logger:
            with patch.object(
                mock_model.objects, "bulk_update"
            ) as mock_bulk_update:
                migration_module.up_log_entries(mock_apps, None)

                assert mock_bulk_update.call_count == 3

                mock_logger.info.assert_any_call(
                    f"{chunk_size} entries are parsed."
                )
                mock_logger.info.assert_any_call(
                    f"{chunk_size * 2} entries are parsed."
                )
                mock_logger.info.assert_any_call(
                    f"Totally {len(mock_entries)} entries are parsed."
                )

                assert mock_extract.call_count == len(mock_entries)


@pytest.mark.django_db
def test_down_log_entries_chunk_size():
    migration_module = import_module(
        "aap_eda.core.migrations.0056_rulebookprocesslog_log_created_at_and_more"  # noqa E501
    )

    mock_apps = MagicMock()
    mock_model = MagicMock()
    mock_apps.get_model.return_value = mock_model

    # Create mock entries exceeding CHUNK_SIZE
    chunk_size = migration_module.CHUNK_SIZE
    mock_entries = [
        MagicMock(id=i, log=f"log {i}", log_created_at=MagicMock())
        for i in range(chunk_size * 2 + 1)
    ]
    mock_model.objects.iterator.return_value = mock_entries

    with patch.object(migration_module, "logger") as mock_logger:
        with patch.object(
            mock_model.objects, "bulk_update"
        ) as mock_bulk_update:
            migration_module.down_log_entries(mock_apps, None)

            # Ensure bulk_update is called the correct number of times
            assert mock_bulk_update.call_count == 3

            # Verify the correct number of entries are passed each time
            bulk_update_calls = mock_bulk_update.call_args_list
            assert len(bulk_update_calls[0][0][0]) == chunk_size  # 1st chunk
            assert len(bulk_update_calls[1][0][0]) == chunk_size  # 2nd chunk
            assert len(bulk_update_calls[2][0][0]) == 1  # Remaining entry

        mock_logger.info.assert_any_call(f"{chunk_size} entries are reversed.")
        mock_logger.info.assert_any_call(
            f"{chunk_size * 2} entries are reversed."
        )
        mock_logger.info.assert_any_call(
            f"Totally {len(mock_entries)} entries are reversed."
        )
