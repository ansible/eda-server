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

import pytest
from ansible_base.rbac import permission_registry
from rest_framework.reverse import reverse

from aap_eda.core import models


@pytest.mark.django_db
@pytest.mark.parametrize("model", permission_registry.all_registered_models)
def test_related_organization_edit_access_control(
    cls_factory, user, user_api_client, give_obj_perm, model
):
    obj = cls_factory.create(model)
    if "change" not in obj._meta.default_permissions:
        pytest.skip("Model has no change permission")
    if "organization" not in [f.name for f in obj._meta.concrete_fields]:
        pytest.skip("Model has no organization field")
    # user has permission to the object but not to its organization
    give_obj_perm(user, obj, "change")
    url = reverse(f"{model._meta.model_name}-detail", kwargs={"pk": obj.pk})

    # since the organization is not changed, access should be allowed
    response = user_api_client.patch(
        url, data={"organization_id": obj.organization.pk}
    )
    assert response.status_code == 200, response.data

    # should not be able to change organization to another organization
    organization = cls_factory.create(models.Organization)
    assert organization.pk != obj.organization_id
    response = user_api_client.patch(
        url, data={"organization_id": organization.pk}
    )
    # views may have inconsistently editable organization fields
    # so no asserts on status here
    obj.refresh_from_db()
    assert organization.pk != obj.organization_id


@pytest.mark.skip(reason="will be reenabled by AAP-23288")
@pytest.mark.django_db
def test_project_credential_access(
    cls_factory, user, user_api_client, give_obj_perm
):
    project = cls_factory.create(models.Project)
    give_obj_perm(user, project, "change")
    url = reverse("project-detail", kwargs={"pk": project.pk})

    credential = cls_factory.create(models.EdaCredential)
    assert project.eda_credential_id != credential.pk  # sanity

    response = user_api_client.patch(
        url, data={"eda_credential_id": credential.pk}
    )
    assert response.status_code == 400, response.data
    project.refresh_from_db()
    assert project.eda_credential_id != credential.pk

    give_obj_perm(user, credential, "change")
    response = user_api_client.patch(
        url, data={"eda_credential_id": credential.pk}
    )
    assert response.status_code == 200, response.data
    project.refresh_from_db()
    assert project.eda_credential_id == credential.pk
