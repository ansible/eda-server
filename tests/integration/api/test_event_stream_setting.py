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

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import models
from tests.integration.constants import api_url_v1

SETTINGS_URL = f"{api_url_v1}/event-stream-settings"


@pytest.fixture
def default_event_stream_setting(default_organization):
    return models.EventStreamSetting.objects.create(
        organization=default_organization,
        allowed_ips=["10.0.0.1", "10.0.0.2"],
        blocked_ips=["192.168.1.100"],
        blacklist_threshold=3,
        blacklist_window=30,
        lockout_duration=1800,
    )


@pytest.mark.django_db
class TestEventStreamSettingCreate:
    def test_create(self, admin_client: APIClient, default_organization):
        response = admin_client.post(
            f"{SETTINGS_URL}/",
            data={
                "organization_id": default_organization.id,
                "allowed_ips": ["10.0.0.1"],
                "blocked_ips": [],
                "blacklist_threshold": 5,
                "blacklist_window": 60,
                "lockout_duration": 3600,
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["allowed_ips"] == ["10.0.0.1"]
        assert response.data["blacklist_threshold"] == 5

    def test_create_duplicate_org_rejected(
        self,
        admin_client: APIClient,
        default_event_stream_setting,
        default_organization,
    ):
        response = admin_client.post(
            f"{SETTINGS_URL}/",
            data={
                "organization_id": default_organization.id,
                "allowed_ips": [],
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_with_defaults(
        self, admin_client: APIClient, default_organization
    ):
        response = admin_client.post(
            f"{SETTINGS_URL}/",
            data={"organization_id": default_organization.id},
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["allowed_ips"] == []
        assert response.data["blocked_ips"] == []
        assert response.data["blacklist_threshold"] == 5
        assert response.data["blacklist_window"] == 60
        assert response.data["lockout_duration"] == 3600


@pytest.mark.django_db
class TestEventStreamSettingRead:
    def test_retrieve(
        self,
        admin_client: APIClient,
        default_event_stream_setting,
    ):
        pk = default_event_stream_setting.id
        response = admin_client.get(f"{SETTINGS_URL}/{pk}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["allowed_ips"] == ["10.0.0.1", "10.0.0.2"]
        assert response.data["organization"] is not None

    def test_list(
        self,
        admin_client: APIClient,
        default_event_stream_setting,
    ):
        response = admin_client.get(f"{SETTINGS_URL}/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1


@pytest.mark.django_db
class TestEventStreamSettingUpdate:
    def test_partial_update_allowed_ips(
        self,
        admin_client: APIClient,
        default_event_stream_setting,
    ):
        pk = default_event_stream_setting.id
        response = admin_client.patch(
            f"{SETTINGS_URL}/{pk}/",
            data={"allowed_ips": ["172.16.0.1"]},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["allowed_ips"] == ["172.16.0.1"]

    def test_partial_update_lockout_duration(
        self,
        admin_client: APIClient,
        default_event_stream_setting,
    ):
        pk = default_event_stream_setting.id
        response = admin_client.patch(
            f"{SETTINGS_URL}/{pk}/",
            data={"lockout_duration": 7200},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["lockout_duration"] == 7200


@pytest.mark.django_db
class TestEventStreamSettingValidation:
    def test_invalid_ip_rejected(
        self, admin_client: APIClient, default_organization
    ):
        response = admin_client.post(
            f"{SETTINGS_URL}/",
            data={
                "organization_id": default_organization.id,
                "allowed_ips": ["not-an-ip"],
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_max_255_ips_enforced(
        self, admin_client: APIClient, default_organization
    ):
        ips = [f"10.0.{i // 256}.{i % 256}" for i in range(256)]
        response = admin_client.post(
            f"{SETTINGS_URL}/",
            data={
                "organization_id": default_organization.id,
                "allowed_ips": ips,
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_ipv6_accepted(
        self, admin_client: APIClient, default_organization
    ):
        response = admin_client.post(
            f"{SETTINGS_URL}/",
            data={
                "organization_id": default_organization.id,
                "allowed_ips": ["::1", "2001:db8::1"],
            },
        )
        assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
class TestClearBlocked:
    def test_clear_blocked(
        self,
        admin_client: APIClient,
        default_event_stream_setting,
    ):
        pk = default_event_stream_setting.id
        assert default_event_stream_setting.blocked_ips == ["192.168.1.100"]
        response = admin_client.post(
            f"{SETTINGS_URL}/{pk}/clear-blocked/",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["blocked_ips"] == []
        default_event_stream_setting.refresh_from_db()
        assert default_event_stream_setting.blocked_ips == []
