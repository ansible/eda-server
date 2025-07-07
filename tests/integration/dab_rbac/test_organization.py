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
from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.test import override_settings
from django.urls.exceptions import NoReverseMatch
from rest_framework.reverse import reverse


def has_field(cls, field_name):
    try:
        cls._meta.get_field(field_name)
        return True
    except FieldDoesNotExist:
        return False


ORG_MODELS = [
    cls
    for cls in apps.all_models["core"].values()
    if has_field(cls, "organization")
]


@pytest.mark.django_db
@pytest.mark.parametrize("model", ORG_MODELS)
def test_create_with_default_org(cls_factory, model, admin_client, request):
    model_name = cls_factory.get_model_name(model)
    model_obj = cls_factory.get_fixture_object(request, model_name)
    post_data = cls_factory.get_post_data(model_obj)
    assert "organization_id" in post_data  # sanity

    if model._meta.model_name == "team":
        pytest.skip("Team model requires an organization")

    try:
        url = reverse(f"{model._meta.model_name}-list")
    except NoReverseMatch:
        pytest.skip("Not testing model for now")

    with override_settings(EVENT_STREAM_BASE_URL="https://www.example.com/"):
        response = admin_client.post(url, data=post_data, format="json")

    if response.status_code == 405:
        pytest.skip("Not testing model not allowing creation for now")

    assert response.status_code == 201, response.data

    if model.objects.count() == 1:
        obj = model.objects.first()
    elif "name" in response.data:
        obj = model.objects.get(name=response.data["name"])
    else:
        obj = model.objects.get(pk=response.data["id"])

    assert obj.organization_id
    assert obj.organization.name == "Default"


@pytest.mark.django_db
@pytest.mark.parametrize("model", ORG_MODELS)
def test_create_with_custom_org(
    use_local_resource_setting,
    cls_factory,
    model,
    superuser_client,
    request,
    new_organization,
):
    model_name = cls_factory.get_model_name(model)
    model_obj = cls_factory.get_fixture_object(request, model_name)
    post_data = cls_factory.get_post_data(model_obj)
    assert "organization_id" in post_data  # sanity
    # factory returns data with default org so we have to change it here
    post_data["organization_id"] = new_organization.id

    try:
        url = reverse(f"{model._meta.model_name}-list")
    except NoReverseMatch:
        pytest.skip("Not testing model with no list view for now")

    with override_settings(EVENT_STREAM_BASE_URL="https://www.example.com/"):
        response = superuser_client.post(url, data=post_data, format="json")

    if response.status_code == 405:
        pytest.skip("Not testing model not allowing creation for now")

    assert response.status_code == 201, response.data

    if model.objects.count() == 1:
        obj = model.objects.first()
    elif "name" in response.data:
        obj = model.objects.get(name=response.data["name"])
    else:
        obj = model.objects.get(pk=response.data["id"])

    assert obj.organization_id == post_data["organization_id"]
