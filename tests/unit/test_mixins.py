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
    assert dummy_project.modified_at > old_modified_at
