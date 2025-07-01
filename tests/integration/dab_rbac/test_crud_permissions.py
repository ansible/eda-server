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
from ansible_base.rbac.models import DABPermission, RoleDefinition
from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from django.urls.exceptions import NoReverseMatch
from rest_framework.reverse import reverse

from aap_eda.core import models


def get_basename(obj):
    "Return the base of viewset view names for a given object or model"
    if obj._meta.model_name == "rulebookprocess":
        return "activationinstance"
    return obj._meta.model_name


def get_detail_url(obj, skip_if_not_found=False):
    try:
        return reverse(f"{get_basename(obj)}-detail", kwargs={"pk": obj.pk})
    except NoReverseMatch:
        if skip_if_not_found:
            pytest.skip("Missing view is reported in test_view_permissions")
        raise


@pytest.mark.django_db
@pytest.mark.parametrize("model", permission_registry.all_registered_models)
def test_add_permissions(
    request,
    model,
    cls_factory,
    default_user,
    user_client,
    give_obj_perm,
):
    model_name = cls_factory.get_model_name(model)
    model_obj = cls_factory.get_fixture_object(request, model_name)
    post_data = cls_factory.get_post_data(model_obj)

    if "add" not in model._meta.default_permissions:
        pytest.skip("Model has no add permission")

    url = reverse(f"{get_basename(model)}-list")
    with override_settings(EVENT_STREAM_BASE_URL="https://www.example.com/"):
        prior_ct = model.objects.count()
        response = user_client.post(url, data=post_data)
        assert response.status_code == 403, response.data
        assert model.objects.count() == prior_ct  # assure nothing was created

    # Figure out the parent object if we can
    parent_field_name = permission_registry.get_parent_fd_name(model)
    if parent_field_name:
        parent_obj = permission_registry.get_parent_model(model).objects.get(
            id=post_data[parent_field_name]
        )
        add_rd = RoleDefinition.objects.create(
            name=f"add-{model._meta.model_name}",
            content_type=permission_registry.content_type_model.objects.get_for_model(parent_obj),
        )
        add_rd.permissions.add(
            DABPermission.objects.get(codename=f"add_{model._meta.model_name}")
        )
        add_rd.give_permission(default_user, parent_obj)
        assert default_user.has_obj_perm(
            parent_obj, f"add_{model._meta.model_name}"
        )  # sanity
    else:
        # otherwise give global add permission for this model
        add_rd = RoleDefinition.objects.create(
            name=f"add-{model._meta.model_name}-global", content_type=None
        )
        add_rd.give_global_permission(default_user)

    # give user permission to related objects
    # so it does not block the create
    model_names = [
        cls._meta.model_name
        for cls in permission_registry.all_registered_models
    ]
    for field in model._meta.concrete_fields:
        if field.name == parent_field_name:
            continue
        from django.db.models import ForeignKey

        if (
            isinstance(field, ForeignKey)
            and field.related_model._meta.model_name in model_names
        ):
            related_obj = getattr(model_obj, field.name)
            # related object may be optional and empty
            if related_obj:
                related_perm = "change"
                if "change" not in related_obj._meta.default_permissions:
                    related_perm = "view"
                give_obj_perm(default_user, related_obj, related_perm)

    with override_settings(EVENT_STREAM_BASE_URL="https://www.example.com/"):
        response = user_client.post(url, data=post_data, format="json")
        assert response.status_code == 201, response.data

    if model.objects.count() == 1:
        obj = model.objects.first()
    else:
        obj = model.objects.get(pk=response.data["id"])
    if parent_field_name:
        assert obj.organization_id == parent_obj.id

    # Assure that user gets some creator permissions
    assert default_user.has_obj_perm(obj, "view")

    # Assure OPTIONS show POST action since user has add permission
    response = user_client.options(url)
    assert response.status_code == 200
    assert "actions" in response.data
    assert "POST" in response.data["actions"]


@pytest.mark.django_db
@pytest.mark.parametrize("model", permission_registry.all_registered_models)
def test_view_permissions(
    model, cls_factory, default_user, user_client, give_obj_perm, request
):
    model_name = cls_factory.get_model_name(model)
    obj = cls_factory.get_fixture_object(request, model_name)
    # We are not skipping any models, all models should have view permission

    url = get_detail_url(obj)

    # Subtle - server should not indicate whether object exists or not, 404
    response = user_client.get(url, data={})
    assert response.status_code == 404, response.data

    # with view permission, a GET should be successful
    give_obj_perm(default_user, obj, "view")
    response = user_client.get(url, data={})
    assert response.status_code == 200, response.data

    # Assure GET action is on OPTIONS
    # Assure no POST action on OPTIONS since user has no add permission
    response = user_client.options(url)
    assert response.status_code == 200
    assert "GET" in response.data["actions"]
    assert "POST" not in response.data["actions"]


@pytest.mark.django_db
@pytest.mark.parametrize("model", permission_registry.all_registered_models)
def test_change_permissions(
    model, cls_factory, default_user, user_client, give_obj_perm, request
):
    model_name = cls_factory.get_model_name(model)
    obj = cls_factory.get_fixture_object(request, model_name)
    if "change" not in obj._meta.default_permissions:
        pytest.skip("Model has no change permission")

    url = get_detail_url(obj, skip_if_not_found=True)

    if model_name == "activation":
        obj.is_enabled = False
        obj.save(update_fields=["is_enabled"])

    # Attempted PATCH without permission should give a 403
    give_obj_perm(default_user, obj, "view")
    response = user_client.patch(url, data={})
    assert response.status_code == 403, response.data

    # Test OPTIONS without sufficient permissions
    response = user_client.options(url)
    assert response.status_code == 200
    actions = response.data["actions"]
    assert "GET" in actions
    assert "PATCH" not in actions  # no PATCH or PUT
    assert "PUT" not in actions

    # Give object change permission
    give_obj_perm(default_user, obj, "change")
    response = user_client.patch(url, data={})
    assert response.status_code == 200, response.data

    # Test OPTIONS
    response = user_client.options(url)
    assert response.status_code == 200
    actions = response.data["actions"]
    assert "GET" in actions
    assert "PATCH" in actions


@pytest.mark.django_db
@pytest.mark.parametrize("model", permission_registry.all_registered_models)
def test_delete_permissions(
    model, cls_factory, default_user, user_client, give_obj_perm, request
):
    model_name = cls_factory.get_model_name(model)
    obj = cls_factory.get_fixture_object(request, model_name)
    # default org cannot be deleted, so use new_organization fixture
    if obj._meta.model == models.Organization:
        obj = request.getfixturevalue("new_organization")

    if "delete" not in obj._meta.default_permissions:
        pytest.skip("Model has no delete permission")

    url = get_detail_url(obj, skip_if_not_found=True)

    # Attempted DELETE without permission should give a 403
    give_obj_perm(default_user, obj, "view")
    response = user_client.delete(url)
    assert response.status_code == 403, response.data

    # Create and give object role
    give_obj_perm(default_user, obj, "delete")
    response = user_client.delete(url)
    assert response.status_code == 204, response.data
