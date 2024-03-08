from collections import defaultdict
from uuid import uuid4

import pytest
from ansible_base.rbac import permission_registry
from ansible_base.rbac.models import RoleDefinition
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import (
    CharField,
    DateTimeField,
    ForeignKey,
    TextField,
    UUIDField,
)
from django.urls.exceptions import NoReverseMatch
from django.utils.timezone import now
from rest_framework.reverse import reverse

from aap_eda.core.models import DABPermission


class ModelFactory:
    """Factory to create objects using an internal dependency store"""

    def __init__(self, user=None, manual_dependencies=None):
        self.create_idx = 0
        self.name_idx = 0
        self.objects = []
        if user:
            self.objects.append(user)
        self.in_progress = defaultdict(lambda: 0)

    def make_name(self):
        self.name_idx += 1
        return f"factory-object-{self.create_idx}"

    def fk_fields(self, cls):
        for field in cls._meta.concrete_fields:
            if isinstance(field, ForeignKey):
                yield field

    def cls_is_ready(self, cls):
        "True or False, this class can be created with existing dependencies"
        for field in self.fk_fields(cls):
            if field.null is True:
                continue
            if not any(
                isinstance(existing_obj, field.related_model)
                for existing_obj in self.objects
            ):
                return False
        return True

    def get_ready_field(self, cls, related_field_names):
        "Return names of ForeignKey fields without missing dependencies"
        for field_name in related_field_names:
            field = cls._meta.get_field(field_name)
            if self.cls_is_ready(field.related_model):
                return field_name
        return None

    def get_sclar_data(self, cls):
        data = {}
        for field in cls._meta.concrete_fields:
            if hasattr(field, "choices") and field.choices:
                data[field.name] = field.choices[0][0]
            elif isinstance(field, (TextField, CharField)):
                if field.name == "extra_var":
                    data["extra_var"] = '{"a": "b"}'
                else:
                    data[field.name] = self.make_name()
            elif isinstance(field, UUIDField):
                data[field.name] = uuid4()
            elif isinstance(field, DateTimeField):
                data[field.name] = now()
        return data

    def get_create_data(self, cls):
        data = self.get_sclar_data(cls)

        related_field_names = {field.name for field in self.fk_fields(cls)}

        while related_field_names:
            next_field_name = self.get_ready_field(cls, related_field_names)
            if next_field_name is None:
                next_field_name = list(related_field_names)[0]
            field = cls._meta.get_field(next_field_name)
            with transaction.atomic():
                try:
                    related_obj = self.get_or_create(field.related_model)
                except Exception:
                    # Even if we cannot create a dependencyj,
                    # the original object creation might still work, and this
                    related_obj = None
            if related_obj:
                data[field.name] = related_obj
            related_field_names.remove(next_field_name)
        return data

    def get_post_data(self, cls, create_data):
        data = {}
        for key, value in create_data.copy().items():
            field = cls._meta.get_field(key)
            if isinstance(field, ForeignKey):
                data[key] = value.pk
                # some fields are taken with id, like organization_id
                data[f"{key}_id"] = value.pk
            else:
                data[key] = value
        return data

    def create(self, cls):
        self.in_progress[cls] += 1
        self.create_idx += 1
        kwargs = self.get_create_data(cls)
        obj = cls.objects.create(**kwargs)
        self.in_progress[cls] -= 1
        self.objects.append(obj)
        self.create_idx -= 1
        return obj

    def get_or_create(self, cls):
        for obj in self.objects:
            if isinstance(obj, cls):
                return obj
        # Allow a _little_ recursion, but not too much
        if self.in_progress[cls] >= 1:
            return None
        return self.create(cls)


@pytest.fixture
def cls_factory(user):
    return ModelFactory(user)


def give_action_perm(user, obj, action):
    """Give permission to perform an action on an object with DAB RBAC

    Action is named like add, create, or delete
    this creates a role definition with that permission
    then it gives the specified user to the specified object
    """
    ct = ContentType.objects.get_for_model(obj)
    rd = RoleDefinition.objects.create(
        name=f"{obj._meta.model_name}-{action}", content_type=ct
    )
    permissions = [
        DABPermission.objects.get(codename=f"{action}_{obj._meta.model_name}")
    ]
    if action not in ("add", "view"):
        permissions.append(
            DABPermission.objects.get(codename=f"view_{obj._meta.model_name}")
        )
    rd.permissions.add(*permissions)
    rd.give_permission(user, obj)
    return rd


@pytest.mark.django_db
@pytest.mark.parametrize("model", permission_registry.all_registered_models)
def test_factory_sanity(model, cls_factory):
    cls_factory.create(model)


@pytest.mark.django_db
@pytest.mark.parametrize("model", permission_registry.all_registered_models)
def test_add_permissions(model, cls_factory, user, user_api_client):
    create_data = cls_factory.get_create_data(model)
    data = cls_factory.get_post_data(model, create_data)
    if "add" not in model._meta.default_permissions:
        pytest.skip("Model has no add permission")

    url = reverse(f"{model._meta.model_name}-list")

    response = user_api_client.post(url, data=data)
    assert response.status_code == 403, response.data

    # Figure out the parent object if we can
    parent_field_name = permission_registry.get_parent_fd_name(model)
    if parent_field_name:
        parent_obj = create_data[parent_field_name]
        add_rd = RoleDefinition.objects.create(
            name=f"add-{model._meta.model_name}",
            content_type=ContentType.objects.get_for_model(parent_obj),
        )
        add_rd.permissions.add(
            DABPermission.objects.get(codename=f"add_{model._meta.model_name}")
        )
        add_rd.give_permission(user, parent_obj)
        assert user.has_obj_perm(
            parent_obj, f"add_{model._meta.model_name}"
        )  # sanity
    else:
        # otherwise give global add permission for this model
        add_rd = RoleDefinition.objects.create(
            name=f"add-{model._meta.model_name}-global", content_type=None
        )
        add_rd.give_global_permission(user)

    response = user_api_client.post(url, data=data, format="json")
    assert response.status_code == 201, response.data


def get_detail_url(obj, skip_if_not_found=False):
    try:
        return reverse(f"{obj._meta.model_name}-detail", kwargs={"pk": obj.pk})
    except NoReverseMatch:
        if skip_if_not_found:
            pytest.skip("Missing view is reported in test_view_permissions")
        raise


@pytest.mark.django_db
@pytest.mark.parametrize("model", permission_registry.all_registered_models)
def test_view_permissions(model, cls_factory, user, user_api_client):
    obj = cls_factory.create(model)
    # We are not skipping any models, all models should have view permission

    url = get_detail_url(obj)

    # Subtle - server should not indicate whether object exists or not, 404
    response = user_api_client.get(url, data={})
    assert response.status_code == 404, response.data

    # with view permission, a GET should be successful
    give_action_perm(user, obj, "view")
    response = user_api_client.get(url, data={})
    assert response.status_code == 200, response.data


@pytest.mark.django_db
@pytest.mark.parametrize("model", permission_registry.all_registered_models)
def test_change_permissions(model, cls_factory, user, user_api_client):
    obj = cls_factory.create(model)
    if "change" not in obj._meta.default_permissions:
        pytest.skip("Model has no change permission")

    url = get_detail_url(obj, skip_if_not_found=True)

    # Attempted PATCH without permission should give a 403
    give_action_perm(user, obj, "view")
    response = user_api_client.patch(url, data={})
    assert response.status_code == 403, response.data

    # Give object change permission
    give_action_perm(user, obj, "change")
    response = user_api_client.patch(url, data={})
    assert response.status_code == 200, response.data


@pytest.mark.django_db
@pytest.mark.parametrize("model", permission_registry.all_registered_models)
def test_delete_permissions(model, cls_factory, user, user_api_client):
    obj = cls_factory.create(model)
    if "delete" not in obj._meta.default_permissions:
        pytest.skip("Model has no delete permission")

    url = get_detail_url(obj, skip_if_not_found=True)

    # Attempted DELETE without permission should give a 403
    give_action_perm(user, obj, "view")
    response = user_api_client.delete(url)
    assert response.status_code == 403, response.data

    # Create and give object role
    give_action_perm(user, obj, "delete")
    response = user_api_client.delete(url)
    assert response.status_code == 204, response.data
