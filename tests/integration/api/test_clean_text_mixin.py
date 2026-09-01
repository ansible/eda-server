#  Copyright 2026 Red Hat, Inc.
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
"""Integration tests verifying CleanTextMixin is correctly wired to EDA
serializers.

These tests verify that the CleanTextMixin validation (two-tier text
validation with grandfathering) works correctly on all EDA serializers
that were updated in AAP-78702.

The validation is gated behind ENHANCED_INPUT_VALIDATION_ENABLED, so all
test classes use @override_settings to enable it.
"""
from types import SimpleNamespace
from unittest import mock
from unittest.mock import patch

import pytest
from django.conf import settings
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.api.serializers.credential_input_source import (
    CredentialInputSourceUpdateSerializer,
)
from aap_eda.api.serializers.credential_type import (
    CredentialTypeCreateSerializer,
)
from aap_eda.api.serializers.decision_environment import (
    DecisionEnvironmentCreateSerializer,
)
from aap_eda.api.serializers.eda_credential import (
    EdaCredentialCreateSerializer,
    EdaCredentialUpdateSerializer,
)
from aap_eda.api.serializers.event_stream import EventStreamInSerializer
from aap_eda.api.serializers.project import (
    ProjectCreateRequestSerializer,
    ProjectUpdateRequestSerializer,
)
from aap_eda.api.serializers.user import AwxTokenCreateSerializer
from aap_eda.core import enums, models
from tests.integration.constants import api_url_v1

DANGEROUS_NAME = "<script>alert(1)</script>"
DANGEROUS_TEXT = "$(rm -rf /)"
VALID_NAME = "Valid Resource Name"
VALID_USERNAME = "valid.user123"


@override_settings(ENHANCED_INPUT_VALIDATION_ENABLED=True)
@pytest.mark.django_db
class TestOrganizationCleanText:
    """Test CleanTextMixin integration with OrganizationSerializer."""

    def test_rejects_invalid_name_on_create(
        self, use_local_resource_setting, superuser_client: APIClient
    ):
        response = superuser_client.post(
            f"{api_url_v1}/organizations/", data={"name": DANGEROUS_NAME}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "name" in response.data

    def test_accepts_valid_name_on_create(
        self, use_local_resource_setting, superuser_client: APIClient
    ):
        response = superuser_client.post(
            f"{api_url_v1}/organizations/", data={"name": VALID_NAME}
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == VALID_NAME

    def test_rejects_invalid_description_on_create(
        self, use_local_resource_setting, superuser_client: APIClient
    ):
        response = superuser_client.post(
            f"{api_url_v1}/organizations/",
            data={"name": VALID_NAME, "description": DANGEROUS_TEXT},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "description" in response.data

    def test_grandfather_unchanged_name_on_update(
        self,
        use_local_resource_setting,
        new_organization: models.Organization,
        superuser_client: APIClient,
    ):
        models.Organization.objects.filter(pk=new_organization.pk).update(
            name="name;semicolon"
        )
        response = superuser_client.patch(
            f"{api_url_v1}/organizations/{new_organization.id}/",
            data={
                "name": "name;semicolon",
                "description": "Updated description",
            },
        )
        assert response.status_code == status.HTTP_200_OK

    def test_rejects_changed_invalid_name_on_update(
        self,
        use_local_resource_setting,
        new_organization: models.Organization,
        superuser_client: APIClient,
    ):
        response = superuser_client.patch(
            f"{api_url_v1}/organizations/{new_organization.id}/",
            data={"name": DANGEROUS_NAME},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "name" in response.data


@override_settings(ENHANCED_INPUT_VALIDATION_ENABLED=True)
@pytest.mark.django_db
class TestTeamCleanText:
    """Test CleanTextMixin integration with TeamSerializer."""

    def test_rejects_invalid_name_on_create(
        self,
        use_local_resource_setting,
        default_organization: models.Organization,
        admin_client: APIClient,
    ):
        data_in = {
            "name": DANGEROUS_NAME,
            "organization_id": default_organization.id,
        }
        response = admin_client.post(f"{api_url_v1}/teams/", data=data_in)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "name" in response.data

    def test_accepts_valid_name_on_create(
        self,
        use_local_resource_setting,
        default_organization: models.Organization,
        admin_client: APIClient,
    ):
        data_in = {
            "name": VALID_NAME,
            "organization_id": default_organization.id,
        }
        response = admin_client.post(f"{api_url_v1}/teams/", data=data_in)
        assert response.status_code == status.HTTP_201_CREATED

    def test_rejects_invalid_description_on_create(
        self,
        use_local_resource_setting,
        default_organization: models.Organization,
        admin_client: APIClient,
    ):
        data_in = {
            "name": VALID_NAME,
            "description": DANGEROUS_TEXT,
            "organization_id": default_organization.id,
        }
        response = admin_client.post(f"{api_url_v1}/teams/", data=data_in)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "description" in response.data

    def test_grandfather_unchanged_name_on_update(
        self,
        use_local_resource_setting,
        default_team: models.Team,
        admin_client: APIClient,
    ):
        models.Team.objects.filter(pk=default_team.pk).update(
            name="team<invalid>"
        )
        response = admin_client.patch(
            f"{api_url_v1}/teams/{default_team.id}/",
            data={
                "name": "team<invalid>",
                "description": "Updated",
            },
        )
        assert response.status_code == status.HTTP_200_OK


@override_settings(ENHANCED_INPUT_VALIDATION_ENABLED=True)
@pytest.mark.django_db
class TestUserCleanText:
    """Test CleanTextMixin integration with UserSerializer /
    UserUpdateSerializerBase.
    """

    def test_rejects_invalid_username_on_create(
        self, use_local_resource_setting, admin_client: APIClient
    ):
        data_in = {"username": DANGEROUS_NAME, "password": "secret"}
        response = admin_client.post(f"{api_url_v1}/users/", data=data_in)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "username" in response.data

    def test_accepts_valid_username_on_create(
        self, use_local_resource_setting, admin_client: APIClient
    ):
        data_in = {"username": VALID_USERNAME, "password": "secret"}
        response = admin_client.post(f"{api_url_v1}/users/", data=data_in)
        assert response.status_code == status.HTTP_201_CREATED

    def test_rejects_invalid_first_name_on_create(
        self, use_local_resource_setting, admin_client: APIClient
    ):
        data_in = {
            "username": VALID_USERNAME,
            "password": "secret",
            "first_name": DANGEROUS_TEXT,
        }
        response = admin_client.post(f"{api_url_v1}/users/", data=data_in)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "first_name" in response.data

    def test_rejects_invalid_last_name_on_create(
        self, use_local_resource_setting, admin_client: APIClient
    ):
        data_in = {
            "username": VALID_USERNAME,
            "password": "secret",
            "last_name": DANGEROUS_TEXT,
        }
        response = admin_client.post(f"{api_url_v1}/users/", data=data_in)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "last_name" in response.data

    def test_grandfather_unchanged_username_on_update(
        self, use_local_resource_setting, admin_client: APIClient
    ):
        data_in = {"username": "temp.user", "password": "secret"}
        response = admin_client.post(f"{api_url_v1}/users/", data=data_in)
        assert response.status_code == status.HTTP_201_CREATED
        user_id = response.data["id"]

        models.User.objects.filter(pk=user_id).update(username="user;invalid")
        response = admin_client.patch(
            f"{api_url_v1}/users/{user_id}/",
            data={"username": "user;invalid", "first_name": "Updated"},
        )
        assert response.status_code == status.HTTP_200_OK

    def test_rejects_changed_invalid_username_on_update(
        self,
        use_local_resource_setting,
        admin_client: APIClient,
        admin_user: models.User,
    ):
        response = admin_client.patch(
            f"{api_url_v1}/users/{admin_user.id}/",
            data={"username": DANGEROUS_NAME},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "username" in response.data


@override_settings(ENHANCED_INPUT_VALIDATION_ENABLED=True)
@pytest.mark.django_db
class TestActivationCleanText:
    """Test CleanTextMixin integration with ActivationCreateSerializer /
    ActivationUpdateSerializer.
    """

    @mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
    @patch(
        "aap_eda.api.views.activation.check_dispatcherd_workers_health",
        return_value=True,
    )
    def test_rejects_invalid_name_on_create(
        self,
        mock_health_check,
        admin_awx_token: models.AwxToken,
        activation_payload: dict,
        admin_client: APIClient,
    ):
        activation_payload["name"] = DANGEROUS_NAME
        response = admin_client.post(
            f"{api_url_v1}/activations/", data=activation_payload
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "name" in response.data

    @mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
    @patch(
        "aap_eda.api.views.activation.check_dispatcherd_workers_health",
        return_value=True,
    )
    def test_accepts_valid_name_on_create(
        self,
        mock_health_check,
        admin_awx_token: models.AwxToken,
        activation_payload: dict,
        admin_client: APIClient,
    ):
        response = admin_client.post(
            f"{api_url_v1}/activations/", data=activation_payload
        )
        assert response.status_code == status.HTTP_201_CREATED

    @mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
    @patch(
        "aap_eda.api.views.activation.check_dispatcherd_workers_health",
        return_value=True,
    )
    def test_grandfather_unchanged_description_on_update(
        self,
        mock_health_check,
        admin_awx_token: models.AwxToken,
        activation_payload: dict,
        admin_client: APIClient,
    ):
        activation_payload["is_enabled"] = False
        response = admin_client.post(
            f"{api_url_v1}/activations/", data=activation_payload
        )
        assert response.status_code == status.HTTP_201_CREATED
        activation_id = response.data["id"]

        models.Activation.objects.filter(pk=activation_id).update(
            description="description;semicolon"
        )
        response = admin_client.patch(
            f"{api_url_v1}/activations/{activation_id}/",
            data={"description": "description;semicolon"},
        )
        assert response.status_code == status.HTTP_200_OK

    @mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
    @patch(
        "aap_eda.api.views.activation.check_dispatcherd_workers_health",
        return_value=True,
    )
    def test_rejects_changed_invalid_description_on_update(
        self,
        mock_health_check,
        admin_awx_token: models.AwxToken,
        activation_payload: dict,
        admin_client: APIClient,
    ):
        activation_payload["is_enabled"] = False
        response = admin_client.post(
            f"{api_url_v1}/activations/", data=activation_payload
        )
        assert response.status_code == status.HTTP_201_CREATED
        activation_id = response.data["id"]

        response = admin_client.patch(
            f"{api_url_v1}/activations/{activation_id}/",
            data={"description": DANGEROUS_TEXT},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "description" in response.data

    @mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
    @patch(
        "aap_eda.api.views.activation.check_dispatcherd_workers_health",
        return_value=True,
    )
    def test_copy_propagates_valid_description(
        self,
        mock_health_check,
        admin_awx_token: models.AwxToken,
        activation_payload: dict,
        admin_client: APIClient,
    ):
        response = admin_client.post(
            f"{api_url_v1}/activations/", data=activation_payload
        )
        assert response.status_code == status.HTTP_201_CREATED
        activation_id = response.data["id"]

        response = admin_client.post(
            f"{api_url_v1}/activations/{activation_id}/copy/",
            data={"name": "copied-activation"},
        )
        assert response.status_code == status.HTTP_201_CREATED
        copied = models.Activation.objects.get(name="copied-activation")
        assert copied.description == activation_payload["description"]

    @mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
    @patch(
        "aap_eda.api.views.activation.check_dispatcherd_workers_health",
        return_value=True,
    )
    def test_rejects_copy_of_grandfathered_invalid_description(
        self,
        mock_health_check,
        admin_awx_token: models.AwxToken,
        activation_payload: dict,
        admin_client: APIClient,
    ):
        """A /copy/ must not propagate blocklisted text into a new row,
        even when the source activation's description was grandfathered
        in (e.g. it predates ENHANCED_INPUT_VALIDATION_ENABLED).
        """
        response = admin_client.post(
            f"{api_url_v1}/activations/", data=activation_payload
        )
        assert response.status_code == status.HTTP_201_CREATED
        activation_id = response.data["id"]

        models.Activation.objects.filter(pk=activation_id).update(
            description=DANGEROUS_TEXT
        )

        response = admin_client.post(
            f"{api_url_v1}/activations/{activation_id}/copy/",
            data={"name": "copied-activation"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not models.Activation.objects.filter(
            name="copied-activation"
        ).exists()


@override_settings(ENHANCED_INPUT_VALIDATION_ENABLED=True)
@pytest.mark.django_db
class TestProjectCleanText:
    """Test CleanTextMixin integration with ProjectCreateRequestSerializer /
    ProjectUpdateRequestSerializer.
    """

    def test_rejects_invalid_name_on_create(
        self, default_organization: models.Organization
    ):
        serializer = ProjectCreateRequestSerializer(
            data={
                "name": DANGEROUS_NAME,
                "url": "https://git.example.com/acme/project-01",
                "organization_id": default_organization.id,
            }
        )
        assert not serializer.is_valid()
        assert "name" in serializer.errors

    def test_accepts_valid_name_on_create(
        self, default_organization: models.Organization
    ):
        serializer = ProjectCreateRequestSerializer(
            data={
                "name": VALID_NAME,
                "url": "https://git.example.com/acme/project-01",
                "organization_id": default_organization.id,
            }
        )
        assert serializer.is_valid(), serializer.errors
        assert "name" not in serializer.errors

    def test_rejects_invalid_description_on_create(
        self, default_organization: models.Organization
    ):
        serializer = ProjectCreateRequestSerializer(
            data={
                "name": VALID_NAME,
                "description": DANGEROUS_TEXT,
                "url": "https://git.example.com/acme/project-01",
                "organization_id": default_organization.id,
            }
        )
        assert not serializer.is_valid()
        assert "description" in serializer.errors

    def test_grandfather_unchanged_name_on_update(
        self, default_project: models.Project
    ):
        models.Project.objects.filter(pk=default_project.pk).update(
            name="project;invalid"
        )
        default_project.refresh_from_db()

        serializer = ProjectUpdateRequestSerializer(
            instance=default_project,
            data={"name": "project;invalid"},
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors

    def test_rejects_changed_invalid_name_on_update(
        self, default_project: models.Project
    ):
        serializer = ProjectUpdateRequestSerializer(
            instance=default_project,
            data={"name": DANGEROUS_NAME},
            partial=True,
        )
        assert not serializer.is_valid()
        assert "name" in serializer.errors


@override_settings(ENHANCED_INPUT_VALIDATION_ENABLED=True)
@pytest.mark.django_db
class TestDecisionEnvironmentCleanText:
    """Test CleanTextMixin integration with
    DecisionEnvironmentCreateSerializer.
    """

    def test_rejects_invalid_name_on_create(
        self, default_organization: models.Organization
    ):
        serializer = DecisionEnvironmentCreateSerializer(
            data={
                "name": DANGEROUS_NAME,
                "image_url": "quay.io/ansible/ansible-rulebook:latest",
                "organization_id": default_organization.id,
            }
        )
        assert not serializer.is_valid()
        assert "name" in serializer.errors

    def test_accepts_valid_name_on_create(
        self, default_organization: models.Organization
    ):
        serializer = DecisionEnvironmentCreateSerializer(
            data={
                "name": VALID_NAME,
                "image_url": "quay.io/ansible/ansible-rulebook:latest",
                "organization_id": default_organization.id,
            }
        )
        assert serializer.is_valid(), serializer.errors

    def test_grandfather_unchanged_name_on_update(
        self, default_decision_environment: models.DecisionEnvironment
    ):
        models.DecisionEnvironment.objects.filter(
            pk=default_decision_environment.pk
        ).update(name="de`invalid")
        default_decision_environment.refresh_from_db()

        serializer = DecisionEnvironmentCreateSerializer(
            instance=default_decision_environment,
            data={"name": "de`invalid"},
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors

    def test_rejects_changed_invalid_name_on_update(
        self, default_decision_environment: models.DecisionEnvironment
    ):
        serializer = DecisionEnvironmentCreateSerializer(
            instance=default_decision_environment,
            data={"name": DANGEROUS_NAME},
            partial=True,
        )
        assert not serializer.is_valid()
        assert "name" in serializer.errors


@override_settings(ENHANCED_INPUT_VALIDATION_ENABLED=True)
@pytest.mark.django_db
class TestCredentialTypeCleanText:
    """Test CleanTextMixin integration with CredentialTypeCreateSerializer."""

    def test_rejects_invalid_name_on_create(self):
        serializer = CredentialTypeCreateSerializer(
            data={"name": DANGEROUS_NAME}
        )
        assert not serializer.is_valid()
        assert "name" in serializer.errors

    def test_accepts_valid_name_on_create(self):
        serializer = CredentialTypeCreateSerializer(data={"name": VALID_NAME})
        assert serializer.is_valid(), serializer.errors

    def test_rejects_invalid_description_on_create(self):
        serializer = CredentialTypeCreateSerializer(
            data={"name": VALID_NAME, "description": DANGEROUS_TEXT}
        )
        assert not serializer.is_valid()
        assert "description" in serializer.errors

    def test_grandfather_unchanged_name_on_update(
        self, credential_type: models.CredentialType
    ):
        models.CredentialType.objects.filter(pk=credential_type.pk).update(
            name="type;invalid"
        )
        credential_type.refresh_from_db()

        serializer = CredentialTypeCreateSerializer(
            instance=credential_type,
            data={"name": "type;invalid"},
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors


@override_settings(ENHANCED_INPUT_VALIDATION_ENABLED=True)
@pytest.mark.django_db
class TestEdaCredentialCleanText:
    """Test CleanTextMixin integration with EdaCredentialCreateSerializer /
    EdaCredentialUpdateSerializer.
    """

    def test_rejects_invalid_name_on_create(
        self,
        default_organization: models.Organization,
        preseed_credential_types,
    ):
        registry_type = models.CredentialType.objects.get(
            name=enums.DefaultCredentialType.REGISTRY
        )
        serializer = EdaCredentialCreateSerializer(
            data={
                "name": DANGEROUS_NAME,
                "credential_type_id": registry_type.id,
                "inputs": {
                    "username": "dummy-user",
                    "password": "dummy-password",
                },
                "organization_id": default_organization.id,
            }
        )
        assert not serializer.is_valid()
        assert "name" in serializer.errors

    def test_accepts_valid_name_on_create(
        self,
        default_organization: models.Organization,
        preseed_credential_types,
    ):
        registry_type = models.CredentialType.objects.get(
            name=enums.DefaultCredentialType.REGISTRY
        )
        serializer = EdaCredentialCreateSerializer(
            data={
                "name": VALID_NAME,
                "credential_type_id": registry_type.id,
                "inputs": {
                    "username": "dummy-user",
                    "password": "dummy-password",
                },
                "organization_id": default_organization.id,
            }
        )
        assert serializer.is_valid(), serializer.errors

    def test_grandfather_unchanged_name_on_update(
        self, default_registry_credential: models.EdaCredential
    ):
        models.EdaCredential.objects.filter(
            pk=default_registry_credential.pk
        ).update(name="cred;invalid")
        default_registry_credential.refresh_from_db()

        serializer = EdaCredentialUpdateSerializer(
            instance=default_registry_credential,
            data={"name": "cred;invalid"},
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors

    def test_rejects_changed_invalid_name_on_update(
        self, default_registry_credential: models.EdaCredential
    ):
        serializer = EdaCredentialUpdateSerializer(
            instance=default_registry_credential,
            data={"name": DANGEROUS_NAME},
            partial=True,
        )
        assert not serializer.is_valid()
        assert "name" in serializer.errors


@override_settings(ENHANCED_INPUT_VALIDATION_ENABLED=True)
@pytest.mark.django_db
class TestEventStreamCleanText:
    """Test CleanTextMixin integration with EventStreamInSerializer."""

    def test_rejects_invalid_name_on_create(
        self,
        default_organization: models.Organization,
        default_user: models.User,
        default_hmac_credential: models.EdaCredential,
    ):
        serializer = EventStreamInSerializer(
            data={
                "name": DANGEROUS_NAME,
                "eda_credential_id": default_hmac_credential.id,
                "organization_id": default_organization.id,
            },
            context={"request": SimpleNamespace(user=default_user)},
        )
        assert not serializer.is_valid()
        assert "name" in serializer.errors

    def test_accepts_valid_name_on_create(
        self,
        default_organization: models.Organization,
        default_user: models.User,
        default_hmac_credential: models.EdaCredential,
    ):
        serializer = EventStreamInSerializer(
            data={
                "name": VALID_NAME,
                "eda_credential_id": default_hmac_credential.id,
                "organization_id": default_organization.id,
            },
            context={"request": SimpleNamespace(user=default_user)},
        )
        assert serializer.is_valid(), serializer.errors

    def test_grandfather_unchanged_name_on_update(
        self, default_event_stream: models.EventStream
    ):
        models.EventStream.objects.filter(pk=default_event_stream.pk).update(
            name="es<invalid>"
        )
        default_event_stream.refresh_from_db()

        serializer = EventStreamInSerializer(
            instance=default_event_stream,
            data={"name": "es<invalid>"},
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors

    def test_rejects_changed_invalid_name_on_update(
        self, default_event_stream: models.EventStream
    ):
        serializer = EventStreamInSerializer(
            instance=default_event_stream,
            data={"name": DANGEROUS_NAME},
            partial=True,
        )
        assert not serializer.is_valid()
        assert "name" in serializer.errors


@override_settings(ENHANCED_INPUT_VALIDATION_ENABLED=True)
@pytest.mark.django_db
class TestCredentialInputSourceCleanText:
    """Test CleanTextMixin integration with
    CredentialInputSourceUpdateSerializer.

    Note: CredentialInputSource has no name field, so only the Tier 2
    (free-text) description field is exercised here.
    """

    def test_rejects_invalid_description_on_update(
        self,
        default_credential_input_source: models.CredentialInputSource,
    ):
        serializer = CredentialInputSourceUpdateSerializer(
            instance=default_credential_input_source,
            data={"description": DANGEROUS_TEXT},
            partial=True,
        )
        assert not serializer.is_valid()
        assert "description" in serializer.errors

    def test_accepts_valid_description_on_update(
        self,
        default_credential_input_source: models.CredentialInputSource,
    ):
        serializer = CredentialInputSourceUpdateSerializer(
            instance=default_credential_input_source,
            data={"description": "A perfectly reasonable description"},
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors

    def test_grandfather_unchanged_description_on_update(
        self,
        default_credential_input_source: models.CredentialInputSource,
    ):
        models.CredentialInputSource.objects.filter(
            pk=default_credential_input_source.pk
        ).update(description="description;semicolon")
        default_credential_input_source.refresh_from_db()

        serializer = CredentialInputSourceUpdateSerializer(
            instance=default_credential_input_source,
            data={"description": "description;semicolon"},
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors


@override_settings(ENHANCED_INPUT_VALIDATION_ENABLED=True)
@pytest.mark.django_db
class TestAwxTokenCleanText:
    """Test CleanTextMixin integration with AwxTokenCreateSerializer."""

    def test_rejects_invalid_name_on_create(self, default_user: models.User):
        serializer = AwxTokenCreateSerializer(
            data={"name": DANGEROUS_NAME, "token": "sometoken"},
            context={"request": SimpleNamespace(user=default_user)},
        )
        assert not serializer.is_valid()
        assert "name" in serializer.errors

    def test_accepts_valid_name_on_create(self, default_user: models.User):
        serializer = AwxTokenCreateSerializer(
            data={"name": VALID_NAME, "token": "sometoken"},
            context={"request": SimpleNamespace(user=default_user)},
        )
        assert serializer.is_valid(), serializer.errors

    def test_rejects_invalid_description_on_create(
        self, default_user: models.User
    ):
        serializer = AwxTokenCreateSerializer(
            data={
                "name": VALID_NAME,
                "token": "sometoken",
                "description": DANGEROUS_TEXT,
            },
            context={"request": SimpleNamespace(user=default_user)},
        )
        assert not serializer.is_valid()
        assert "description" in serializer.errors


@override_settings(ENHANCED_INPUT_VALIDATION_ENABLED=True)
@pytest.mark.django_db
class TestExcludedFieldsCleanText:
    """Test that fields listed in a serializer's excluded_fields bypass
    CleanTextMixin validation.

    Each field below legitimately carries content (Jinja templates,
    secrets, opaque tokens) that would otherwise trip the free-text
    checks, so it must be accepted even when it contains characters
    that are rejected on non-excluded fields like name/description.
    """

    @mock.patch.object(settings, "RULEBOOK_WORKER_QUEUES", [])
    @patch(
        "aap_eda.api.views.activation.check_dispatcherd_workers_health",
        return_value=True,
    )
    def test_activation_extra_var_excluded(
        self,
        mock_health_check,
        admin_awx_token: models.AwxToken,
        activation_payload: dict,
        admin_client: APIClient,
    ):
        activation_payload["extra_var"] = f"dangerous: '{DANGEROUS_TEXT}'"
        response = admin_client.post(
            f"{api_url_v1}/activations/", data=activation_payload
        )
        assert response.status_code == status.HTTP_201_CREATED, response.data

    def test_credential_type_injectors_excluded(self):
        serializer = CredentialTypeCreateSerializer(
            data={
                "name": VALID_NAME,
                "inputs": {
                    "fields": [
                        {
                            "id": "password",
                            "label": "Password",
                            "type": "string",
                        },
                    ]
                },
                "injectors": {"extra_vars": {"password": DANGEROUS_TEXT}},
            }
        )
        assert serializer.is_valid(), serializer.errors

    def test_eda_credential_inputs_excluded(
        self,
        default_organization: models.Organization,
        preseed_credential_types,
    ):
        registry_type = models.CredentialType.objects.get(
            name=enums.DefaultCredentialType.REGISTRY
        )
        serializer = EdaCredentialCreateSerializer(
            data={
                "name": VALID_NAME,
                "credential_type_id": registry_type.id,
                "inputs": {
                    "username": "dummy-user",
                    "password": DANGEROUS_TEXT,
                },
                "organization_id": default_organization.id,
            }
        )
        assert serializer.is_valid(), serializer.errors

    def test_awx_token_excluded(self, default_user: models.User):
        serializer = AwxTokenCreateSerializer(
            data={"name": VALID_NAME, "token": DANGEROUS_TEXT},
            context={"request": SimpleNamespace(user=default_user)},
        )
        assert serializer.is_valid(), serializer.errors

    def test_credential_input_source_metadata_excluded(
        self,
        default_credential_input_source: models.CredentialInputSource,
    ):
        serializer = CredentialInputSourceUpdateSerializer(
            instance=default_credential_input_source,
            data={"metadata": {"secret_path": DANGEROUS_TEXT}},
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors
