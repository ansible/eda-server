import pytest
from rest_framework.reverse import reverse

from aap_eda.core import models


@pytest.mark.django_db
@pytest.mark.parametrize("action", ["enable", "restart", "disable"])
def test_activation_actions(
    cls_factory, user, user_api_client, give_obj_perm, action
):
    activation = cls_factory.create(models.Activation)
    url = reverse(f"activation-{action}", kwargs={"pk": activation.pk})

    # assure GET is not enabled, so we do not have to permission check it
    response = user_api_client.get(url)
    assert response.status_code == 405, response.data

    # no action permission, denied
    give_obj_perm(user, activation, "view")
    response = user_api_client.post(url)
    assert response.status_code == 403, response.data

    # no permission, denied
    give_obj_perm(user, activation, action)
    response = user_api_client.post(url)
    assert response.status_code == 204, response.data
