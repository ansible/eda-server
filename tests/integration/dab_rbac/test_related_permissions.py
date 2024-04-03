import pytest
from ansible_base.rbac import permission_registry
from rest_framework.reverse import reverse

from aap_eda.core import models


@pytest.mark.django_db
@pytest.mark.parametrize("model", permission_registry.all_registered_models)
def test_organization_field_not_editable(
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


@pytest.mark.django_db
def test_project_credential_access(
    cls_factory, user, user_api_client, give_obj_perm
):
    project = cls_factory.create(models.Project)
    give_obj_perm(user, project, "change")
    url = reverse("project-detail", kwargs={"pk": project.pk})

    credential = cls_factory.create(models.Credential)
    assert project.credential_id != credential.pk  # sanity

    response = user_api_client.patch(
        url, data={"credential_id": credential.pk}
    )
    assert response.status_code == 403, response.data
    project.refresh_from_db()
    assert project.credential_id != credential.pk

    give_obj_perm(user, credential, "change")
    response = user_api_client.patch(
        url, data={"credential_id": credential.pk}
    )
    assert response.status_code == 200, response.data
    project.refresh_from_db()
    assert project.credential_id == credential.pk
