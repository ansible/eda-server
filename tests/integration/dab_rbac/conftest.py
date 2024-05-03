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
from ansible_base.rbac.models import DABPermission, RoleDefinition
from django.contrib.contenttypes.models import ContentType
from django.db.models import ForeignKey
from django.forms.models import model_to_dict
from rest_framework.test import APIClient

from aap_eda.core import models
from aap_eda.core.management.commands.create_initial_data import Command
from aap_eda.core.utils.credentials import inputs_to_display


@pytest.fixture
def user_api_client(db, user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def initial_data():
    Command().handle()


class ModelFactory:
    """Factory to build resources post data based on existing fixtures."""

    def get_model_name(self, model):
        name = model._meta.verbose_name.replace(" ", "_")
        if model == models.RulebookProcess:
            name = "activation_instance"
        return name

    def get_fixture_object(self, request, name):
        if name == "rulebook_process":
            name = "activation_instance"
        # default org is immutable
        elif name == "organization":
            return request.getfixturevalue("new_organization")
        return request.getfixturevalue(f"default_{name}")

    def get_post_data(self, model_obj):
        obj_data = model_to_dict(model_obj)
        post_data = {}
        # go through each field and add to post_data
        for key, value in obj_data.items():
            field = model_obj._meta.get_field(key)
            if value:
                post_data[key] = value
                if isinstance(field, ForeignKey):
                    # some fields are taken with id, like organization_id
                    post_data[f"{key}_id"] = value
        # update name since it might conflict with existing fixture name
        post_data["name"] += "-rbac"
        # handle special constraints for models
        if model_obj._meta.model == models.EdaCredential:
            post_data["inputs"] = inputs_to_display(
                model_obj.credential_type.inputs, post_data["inputs"]
            )
        # handle special case of m2m-related fields (like eda_credentials)
        elif model_obj._meta.model == models.Activation:
            related_objs = list(model_obj.eda_credentials.all().values())
            post_data["eda_credentials"] = [obj["id"] for obj in related_objs]
        return post_data


@pytest.fixture
def cls_factory():  # noqa: F811
    return ModelFactory()


@pytest.fixture
def give_obj_perm():
    def _rf(target_user, obj, action):
        """Give permission to perform an action on an object with DAB RBAC

        Action is named like add, create, or delete
        this creates a role definition with that permission
        then it gives the specified user to the specified object
        """
        ct = ContentType.objects.get_for_model(obj)
        rd, _ = RoleDefinition.objects.get_or_create(
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
