from collections import defaultdict
from uuid import uuid4

import pytest
from ansible_base.lib.testing.fixtures import (  # noqa: F401
    admin_api_client,
    local_authenticator,
    unauthenticated_api_client,
    user,
    user_api_client,
)
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
from django.utils.timezone import now

from aap_eda.core.models import DABPermission


class ModelFactory:
    """Factory to create objects using an internal dependency store"""

    def __init__(self, current_user=None, manual_dependencies=None):
        self.create_idx = 0
        self.name_idx = 0
        self.objects = []
        if current_user:
            self.objects.append(current_user)
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
def cls_factory(user):  # noqa: F811
    return ModelFactory(user)


@pytest.fixture
def give_obj_perm():
    def _rf(target_user, obj, action):
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
            DABPermission.objects.get(
                codename=f"{action}_{obj._meta.model_name}"
            )
        ]
        if action not in ("add", "view"):
            permissions.append(
                DABPermission.objects.get(
                    codename=f"view_{obj._meta.model_name}"
                )
            )
        rd.permissions.add(*permissions)
        rd.give_permission(target_user, obj)
        return rd

    return _rf
