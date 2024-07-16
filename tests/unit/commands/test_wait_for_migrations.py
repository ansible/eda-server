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


import time

import pytest
from django.core.management import call_command


@pytest.fixture
def rollback_migration():
    call_command("migrate", "core", "0039")
    yield
    call_command("migrate")


@pytest.mark.django_db
def test_no_pending_migrations(capsys):
    call_command("wait_for_migrations", timeout=1)

    captured = capsys.readouterr()
    assert "All migrations are applied." in captured.out


@pytest.mark.django_db
def test_pending_migrations(capsys, rollback_migration):
    before = time.time()
    with pytest.raises(SystemExit) as excinfo:
        call_command("wait_for_migrations", timeout=3)

    captured = capsys.readouterr()
    assert "Timeout exceeded. There are pending migrations." in captured.err
    assert excinfo.value.code == 1
    assert time.time() - before > 3
