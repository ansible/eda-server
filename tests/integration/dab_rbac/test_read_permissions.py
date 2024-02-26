import pytest
from ansible_base.rbac.models import RoleDefinition
from django.contrib.contenttypes.models import ContentType
from rest_framework.reverse import reverse

from aap_eda.core import models


@pytest.fixture
def activation(user):
    return models.Activation.objects.create(name="activation", user=user)


@pytest.fixture
def rulebook_process(activation):
    return models.RulebookProcess.objects.create(
        name="test-instance", activation=activation
    )


@pytest.fixture
def view_activation_rd(activation):
    return RoleDefinition.objects.create_from_permissions(
        name="view_act",
        content_type=ContentType.objects.get_for_model(activation),
        permissions=["view_activation"],
    )


@pytest.mark.django_db
def test_get_activation(activation, user, user_api_client, view_activation_rd):
    url = reverse("activation-detail", kwargs={"pk": activation.pk})

    assert not user.has_obj_perm(activation, "view")
    r = user_api_client.get(url)
    assert r.status_code == 404

    view_activation_rd.give_permission(user, activation)

    assert user.has_obj_perm(activation, "view")
    r = user_api_client.get(url)
    assert r.status_code == 200


@pytest.mark.django_db
def test_view_assignments_non_admin(
    activation, user, user_api_client, view_activation_rd
):
    assignment = view_activation_rd.give_permission(user, activation)
    url = reverse("roleuserassignment-list")
    r = user_api_client.get(url)
    assert r.status_code == 200
    assert r.data["count"] == 1
    assert r.data["results"][0]["id"] == assignment.id


@pytest.mark.django_db
def test_delete_user_after_assignment(activation, user, view_activation_rd):
    view_activation_rd.give_permission(user, activation)
    user.delete()


# additional views to test
# activation-enable
# rulebook-rulesets
