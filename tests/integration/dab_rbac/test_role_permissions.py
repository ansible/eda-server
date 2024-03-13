import pytest
from ansible_base.rbac.models import RoleDefinition
from django.contrib.contenttypes.models import ContentType
from rest_framework.reverse import reverse

from aap_eda.core import models


@pytest.fixture
def view_activation_rd():
    return RoleDefinition.objects.create_from_permissions(
        name="view_act",
        content_type=ContentType.objects.get_for_model(models.Activation),
        permissions=["view_activation"],
    )


@pytest.mark.django_db
def test_view_assignments_non_admin(
    user, user_api_client, cls_factory, view_activation_rd
):
    activation = cls_factory.create(models.Activation)
    assignment = view_activation_rd.give_permission(user, activation)
    url = reverse("roleuserassignment-list")
    r = user_api_client.get(url)
    assert r.status_code == 200
    assert r.data["count"] == 1
    assert r.data["results"][0]["id"] == assignment.id


@pytest.mark.skip(reason="Not fixed in DAB")
@pytest.mark.django_db
def test_delete_user_after_assignment(user, view_activation_rd, cls_factory):
    activation = cls_factory.create(models.Activation)
    view_activation_rd.give_permission(user, activation)
    user.delete()
