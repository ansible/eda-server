#  Copyright 2023 Red Hat, Inc.
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
import pytest

import aap_eda.core.models as models


@pytest.fixture
def dummy_project(db):
    return models.Project.objects.create(
        name="dummy_project", url="http://dummy_project.com"
    )


@pytest.mark.django_db
def test_modified_at_updater_mixin(dummy_project: models.Project):
    old_modified_at = dummy_project.modified_at
    dummy_project.name = "new_value"
    dummy_project.save(update_fields=["name"])
    dummy_project.refresh_from_db()
    assert dummy_project.modified_at > old_modified_at
