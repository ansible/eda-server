import pytest

from django.contrib.contenttypes.models import ContentType

from rest_framework.reverse import reverse

from ansible_base.rbac.models import RoleDefinition

from aap_eda.core import models


@pytest.fixture
def activation(user):
    return models.Activation.objects.create(name="activation", user=user)


@pytest.fixture
def rulebook_process(activation):
    return models.RulebookProcess.objects.create(name="test-instance", activation=activation)


@pytest.mark.django_db
def test_get_activation(activation, user, user_api_client):
    rd = RoleDefinition.objects.create_from_permissions(
        name='view_act', content_type=ContentType.objects.get_for_model(activation),
        permissions=['view_activation']
    )
    url = reverse('activation-detail', kwargs={'pk': activation.pk})

    assert not user.has_obj_perm(activation, 'view')
    r = user_api_client.get(url)
    assert r.status_code == 404

    rd.give_permission(user, activation)

    assert user.has_obj_perm(activation, 'view')
    r = user_api_client.get(url)
    assert r.status_code == 200


# need to test views
# activation-detail - DONE
# activation-enable
# rulebook-rulesets
