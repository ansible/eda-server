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


@pytest.mark.django_db
@pytest.mark.parametrize("model", permission_registry.all_registered_models)
def test_related_organization_edit_access_control(
    cls_factory,
    default_user,
    user_client,
    give_obj_perm,
    model,
    request,
    new_organization,
):
    model_name = cls_factory.get_model_name(model)
    obj = cls_factory.get_fixture_object(request, model_name)
    if "change" not in obj._meta.default_permissions:
        pytest.skip("Model has no change permission")
    if "organization" not in [f.name for f in obj._meta.concrete_fields]:
        pytest.skip("Model has no organization field")

    if model_name == "activation":
        obj.is_enabled = False
        obj.save(update_fields=["is_enabled"])

    # user has permission to the object but not to its organization
    give_obj_perm(default_user, obj, "change")
    url = reverse(f"{model._meta.model_name}-detail", kwargs={"pk": obj.pk})

    # since the organization is not changed, access should be allowed
    response = user_client.patch(
        url, data={"organization_id": obj.organization.pk}
    )
    assert response.status_code == 200, response.data

    # should not be able to change organization to another organization
    assert new_organization.pk != obj.organization_id
    response = user_client.patch(
        url, data={"organization_id": new_organization.pk}
    )
    # views may have inconsistently editable organization fields
    # so no asserts on status here
    obj.refresh_from_db()
    assert new_organization.pk != obj.organization_id


@pytest.mark.django_db
def test_project_credential_access(
    cls_factory,
    default_user,
    user_client,
    default_project,
    new_scm_credential,
    give_obj_perm,
):
    give_obj_perm(default_user, default_project, "change")
    url = reverse("project-detail", kwargs={"pk": default_project.pk})

    assert default_project.eda_credential_id != new_scm_credential.pk  # sanity

    # User can not view provided credential
    response = user_client.patch(
        url, data={"eda_credential_id": new_scm_credential.pk}
    )
    # NOTE: the ideal would probably be 400, but still a matter of discussion
    assert response.status_code in (403, 400), response.data
    assert "eda_credential" in str(response.data), response.data
    default_project.refresh_from_db()
    assert default_project.eda_credential_id != new_scm_credential.pk

    # view permission is enough to use related credential
    # as defined by ANSIBLE_BASE_CHECK_RELATED_PERMISSIONS
    give_obj_perm(default_user, new_scm_credential, "view")
    response = user_client.patch(
        url, data={"eda_credential_id": new_scm_credential.pk}
    )
    assert response.status_code == 200, response.data
    default_project.refresh_from_db()
    assert default_project.eda_credential_id == new_scm_credential.pk
