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
import yaml
from django.conf import settings
from rest_framework import status

from tests.integration.constants import api_url_v1

OPENAPI_TITLE = settings.SPECTACULAR_SETTINGS["TITLE"]


@pytest.mark.parametrize(
    "path",
    [
        pytest.param("/openapi.json", id="openapi_json"),
        pytest.param("/openapi.yaml", id="openapi_yaml"),
    ],
)
@pytest.mark.django_db
def test_v1_openapi(admin_client, path):
    response = admin_client.get(f"{api_url_v1}{path}")
    assert response.status_code == status.HTTP_200_OK
    data = yaml.safe_load(response.content)
    assert data["info"]["title"] == OPENAPI_TITLE


@pytest.mark.django_db
def test_activation_rule_engine_credential_id_is_optional_in_read_schemas(
    admin_client,
):
    response = admin_client.get(f"{api_url_v1}/openapi.json")
    assert response.status_code == status.HTTP_200_OK

    schemas = response.json()["components"]["schemas"]
    for schema_name in ("ActivationList", "ActivationRead"):
        schema = schemas[schema_name]
        assert "rule_engine_credential_id" not in schema.get("required", [])
        assert schema["properties"]["rule_engine_credential_id"] == {
            "type": "integer",
            "nullable": True,
            "readOnly": True,
        }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path",
    [
        pytest.param("/docs/", id="swagger_ui"),
        pytest.param("/redoc/", id="redoc"),
    ],
)
def test_v1_openapi_ui(admin_client, path):
    response = admin_client.get(f"{api_url_v1}{path}")
    assert response.status_code == status.HTTP_200_OK
    assert OPENAPI_TITLE in response.content.decode()


@pytest.mark.django_db
def test_v1_openapi_credential_type_inputs_schema(admin_client):
    response = admin_client.get(f"{api_url_v1}/openapi.json")
    assert response.status_code == status.HTTP_200_OK
    schemas = response.json()["components"]["schemas"]
    inputs = schemas["CredentialType"]["properties"]["inputs"]
    assert inputs["properties"]["fields"]["items"]["$ref"].endswith(
        "CleanTextNestedStringField"
    )
    assert "metadata" in inputs["properties"]

    for schema_name in ("CredentialTypeCreate", "PatchedCredentialTypeCreate"):
        request_inputs = schemas[schema_name]["properties"]["inputs"]
        assert "type" not in request_inputs
        assert "properties" not in request_inputs
        assert request_inputs["additionalProperties"] is True
        assert request_inputs["example"]["required"] == ["username"]


@pytest.mark.django_db
def test_log_purge_openapi_contract(admin_client):
    response = admin_client.get(f"{api_url_v1}/openapi.json")
    assert response.status_code == status.HTTP_200_OK

    spec = response.json()
    purge_path = next(
        path for path in spec["paths"] if path.endswith("/logs/purge/")
    )
    operation = spec["paths"][purge_path]["post"]
    request_ref = operation["requestBody"]["content"]["application/json"][
        "schema"
    ]["$ref"]
    request_schema = spec["components"]["schemas"][
        request_ref.rsplit("/", 1)[1]
    ]
    request_properties = request_schema["properties"]
    assert set(request_properties) == {
        "before_date",
        "retention_duration",
        "audit_trail",
        "log_delete_batch_size",
        "activation_ids",
        "activation_names",
        "purge-all-logs",
    }
    assert request_properties["audit_trail"]["default"] is True
    assert request_properties["log_delete_batch_size"]["minimum"] == 1
    assert request_properties["log_delete_batch_size"]["maximum"] == 50_000
    assert (
        "default: 10,000"
        in request_properties["log_delete_batch_size"]["description"]
    )
    assert request_properties["purge-all-logs"]["default"] is False
    assert "internal_job_uuid" not in request_properties

    responses = operation["responses"]
    assert {"202", "400", "403"}.issubset(responses)
    response_ref = responses["202"]["content"]["application/json"]["schema"][
        "$ref"
    ]
    response_schema = spec["components"]["schemas"][
        response_ref.rsplit("/", 1)[1]
    ]
    assert set(response_schema["properties"]) == {"job_id"}
