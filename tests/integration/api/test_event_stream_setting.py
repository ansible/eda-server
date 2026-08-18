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

import hashlib
import hmac
import secrets

import pytest
from rest_framework import status
from rest_framework.renderers import JSONRenderer
from rest_framework.test import APIClient

from aap_eda.core import models
from tests.integration.api.test_event_stream import (
    create_event_stream,
    create_event_stream_credential,
    event_stream_post_url,
    get_default_test_org,
)
from tests.integration.constants import api_url_v1

SETTINGS_URL = f"{api_url_v1}/event-stream-settings"


@pytest.fixture
def default_event_stream_setting(default_organization):
    return models.EventStreamSetting.objects.create(
        organization=default_organization,
        allowed_ips=["10.0.0.1", "10.0.0.2"],
        blocked_ips=["192.168.1.100"],
    )


@pytest.mark.django_db
class TestEventStreamSettingCreate:
    def test_create(
        self,
        admin_client: APIClient,
        default_organization,
    ):
        response = admin_client.post(
            f"{SETTINGS_URL}/",
            data={
                "organization_id": default_organization.id,
                "allowed_ips": ["10.0.0.1"],
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["allowed_ips"] == ["10.0.0.1"]
        assert response.data["blocked_ips"] == []

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
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_with_defaults(
        self,
        admin_client: APIClient,
        default_organization,
    ):
        response = admin_client.post(
            f"{SETTINGS_URL}/",
            data={
                "organization_id": default_organization.id,
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["allowed_ips"] == []
        assert response.data["blocked_ips"] == []


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
        assert response.data["allowed_ips"] == [
            "10.0.0.1",
            "10.0.0.2",
        ]
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

    def test_adding_to_allowlist_removes_from_blocked(
        self,
        admin_client: APIClient,
        default_event_stream_setting,
    ):
        pk = default_event_stream_setting.id
        assert "192.168.1.100" in (default_event_stream_setting.blocked_ips)
        response = admin_client.patch(
            f"{SETTINGS_URL}/{pk}/",
            data={
                "allowed_ips": [
                    "10.0.0.1",
                    "10.0.0.2",
                    "192.168.1.100",
                ],
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert "192.168.1.100" in response.data["allowed_ips"]
        assert "192.168.1.100" not in response.data["blocked_ips"]


@pytest.mark.django_db
class TestEventStreamSettingValidation:
    @pytest.mark.parametrize(
        "bad_entry",
        [
            "not-an-ip",
            "999.999.999.999",
            "192.168.1",
            "192.168.1.1.1",
            "",
            "abc::xyz",
        ],
    )
    def test_malformed_ip_rejected(
        self,
        admin_client: APIClient,
        default_organization,
        bad_entry,
    ):
        response = admin_client.post(
            f"{SETTINGS_URL}/",
            data={
                "organization_id": default_organization.id,
                "allowed_ips": [bad_entry],
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.parametrize(
        "bad_cidr",
        [
            "192.168.1.0/abc",
            "192.168.1.0/33",
            "192.168.1.0/-1",
            "not-a-network/24",
            "/24",
            "192.168.1.0/",
        ],
    )
    def test_malformed_cidr_rejected(
        self,
        admin_client: APIClient,
        default_organization,
        bad_cidr,
    ):
        response = admin_client.post(
            f"{SETTINGS_URL}/",
            data={
                "organization_id": default_organization.id,
                "allowed_ips": [bad_cidr],
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_max_255_ips_enforced(
        self,
        admin_client: APIClient,
        default_organization,
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
        self,
        admin_client: APIClient,
        default_organization,
    ):
        response = admin_client.post(
            f"{SETTINGS_URL}/",
            data={
                "organization_id": default_organization.id,
                "allowed_ips": ["::1", "2001:db8::1"],
            },
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_cidr_accepted(
        self,
        admin_client: APIClient,
        default_organization,
    ):
        response = admin_client.post(
            f"{SETTINGS_URL}/",
            data={
                "organization_id": default_organization.id,
                "allowed_ips": [
                    "192.30.252.0/22",
                    "10.0.0.1",
                    "2a0a:a440::/29",
                ],
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert "192.30.252.0/22" in response.data["allowed_ips"]


@pytest.mark.django_db
class TestRemoveBlocked:
    def test_remove_specific_ips(
        self,
        admin_client: APIClient,
        default_event_stream_setting,
    ):
        pk = default_event_stream_setting.id
        response = admin_client.post(
            f"{SETTINGS_URL}/{pk}/remove-blocked/",
            data={"ips": ["192.168.1.100"]},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["blocked_ips"] == []

    def test_clear_all_blocked(
        self,
        admin_client: APIClient,
        default_event_stream_setting,
    ):
        pk = default_event_stream_setting.id
        response = admin_client.post(
            f"{SETTINGS_URL}/{pk}/clear-blocked/",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["blocked_ips"] == []
        default_event_stream_setting.refresh_from_db()
        assert default_event_stream_setting.blocked_ips == []


def _create_hmac_event_stream(admin_client, org):
    """Create an HMAC-authenticated event stream for IP policy tests."""
    secret = secrets.token_hex(32)
    header_key = "X-Hub-Signature"
    cred = create_event_stream_credential(
        admin_client,
        "HMAC Event Stream",
        {
            "auth_type": "hmac",
            "secret": secret,
            "http_header_key": header_key,
            "hash_algorithm": "sha256",
            "signature_encoding": "hex",
        },
        name="ip-policy-test-cred",
    )
    es = create_event_stream(
        admin_client,
        {
            "name": "ip-policy-test-es",
            "event_stream_type": cred["credential_type"]["kind"],
            "eda_credential_id": cred["id"],
            "organization_id": org.id,
        },
    )
    return es, secret, header_key


@pytest.mark.django_db
class TestIpPolicyOnPost:
    def test_allowlist_rejects_unlisted_ip(
        self,
        admin_client: APIClient,
        preseed_credential_types,
    ):
        org = get_default_test_org()
        es, secret, header_key = _create_hmac_event_stream(admin_client, org)
        models.EventStreamSetting.objects.create(
            organization=org,
            allowed_ips=["192.168.1.1"],
        )
        data = {"test": "payload"}
        data_bytes = JSONRenderer().render(data)
        sig = hmac.new(
            secret.encode(), msg=data_bytes, digestmod=hashlib.sha256
        ).hexdigest()
        response = admin_client.post(
            event_stream_post_url(es.uuid),
            headers={header_key: sig},
            data=data,
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_no_settings_allows_request(
        self,
        admin_client: APIClient,
        preseed_credential_types,
    ):
        org = get_default_test_org()
        es, secret, header_key = _create_hmac_event_stream(admin_client, org)
        data = {"test": "payload"}
        data_bytes = JSONRenderer().render(data)
        sig = hmac.new(
            secret.encode(), msg=data_bytes, digestmod=hashlib.sha256
        ).hexdigest()
        response = admin_client.post(
            event_stream_post_url(es.uuid),
            headers={header_key: sig},
            data=data,
        )
        assert response.status_code == status.HTTP_200_OK

    def test_rejection_records_blocked_ip(
        self,
        admin_client: APIClient,
        preseed_credential_types,
    ):
        org = get_default_test_org()
        es, _, _ = _create_hmac_event_stream(admin_client, org)
        setting = models.EventStreamSetting.objects.create(
            organization=org,
            allowed_ips=["192.168.1.1"],
        )
        admin_client.post(
            event_stream_post_url(es.uuid),
            data={"test": "payload"},
        )
        setting.refresh_from_db()
        assert len(setting.blocked_ips) > 0
