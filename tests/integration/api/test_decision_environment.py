from dataclasses import dataclass

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from aap_eda.core import models
from tests.integration.constants import api_url_v1


@dataclass
class InitData:
    project: models.Project
    activation: models.Activation
    decision_environment: models.DecisionEnvironment
    credential: models.Credential
    rulebook: models.Rulebook
    ruleset: models.Ruleset
    rule: models.Rule
    activation_instance: models.ActivationInstance


@pytest.mark.django_db
def test_list_decision_environments(client: APIClient):
    credential = models.Credential.objects.create(name="credential1", username="me", secret="sec1")
    obj = models.DecisionEnvironment.objects.create(
        name="de1", image_url="registry.com/img1:tag1", credential=credential
    )
    response = client.get(f"{api_url_v1}/decision-environments/")
    assert response.status_code == status.HTTP_200_OK
    result = response.data["results"][0]
    result.pop("created_at")
    result.pop("modified_at")
    assert result == {
        "name": "de1",
        "description": "",
        "image_url": "registry.com/img1:tag1",
        "credential_id": credential.id,
        "id": obj.id,
    }


@pytest.mark.django_db
def test_create_decision_environment(client: APIClient):
    credential = models.Credential.objects.create(name="credential1", username="me", secret="sec1")
    data_in = {
        "name": "de1",
        "description": "desc here",
        "image_url": "registry.com/img1:tag1",
        "credential_id": credential.id,
    }
    response = client.post(f"{api_url_v1}/decision-environments/", data=data_in)
    assert response.status_code == status.HTTP_201_CREATED
    id_ = response.data["id"]
    result = response.data
    result.pop("created_at")
    result.pop("modified_at")
    assert result == {
        "name": "de1",
        "description": "desc here",
        "image_url": "registry.com/img1:tag1",
        "credential_id": credential.id,
        "id": id_,
    }
    assert models.DecisionEnvironment.objects.filter(pk=id_).exists()


@pytest.mark.django_db
def test_retrieve_decision_environment(client: APIClient, init_db):
    credential = init_db.credential
    obj = init_db.decision_environment

    response = client.get(f"{api_url_v1}/decision-environments/{obj.id}/")
    assert response.status_code == status.HTTP_200_OK
    result = response.data
    result.pop("created_at")
    result.pop("modified_at")
    assert result == {
        "id": obj.id,
        "name": "de1",
        "description": "",
        "image_url": "registry.com/img1:tag1",
        "credential": {
            "id": credential.id,
            "name": credential.name,
            "description": credential.description,
            "credential_type": credential.credential_type,
            "username": credential.username,
        },
    }


@pytest.mark.django_db
def test_retrieve_decision_environment_not_exist(client: APIClient):
    response = client.get(f"{api_url_v1}/decision-environments/42/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_partial_update_decision_environment(client: APIClient, init_db):
    obj = init_db.decision_environment
    credential = models.Credential.objects.create(name="newcredential", username="me2", secret="sec2")
    data = {"credential_id": credential.id}
    response = client.patch(f"{api_url_v1}/decision-environments/{obj.id}/", data=data)
    assert response.status_code == status.HTTP_200_OK
    result = response.data
    result.pop("created_at")
    result.pop("modified_at")
    assert result == {
        "name": "de1",
        "description": "",
        "image_url": "registry.com/img1:tag1",
        "credential_id": credential.id,
        "id": obj.id,
    }
    updated_obj = models.DecisionEnvironment.objects.filter(pk=int(obj.id)).first()
    assert updated_obj.credential == credential


@pytest.mark.django_db
def test_delete_decision_environment_conflict(client: APIClient, init_db):
    obj_id = int(init_db.decision_environment.id)
    response = client.delete(f"{api_url_v1}/decision-environments/{obj_id}/")
    assert response.status_code == status.HTTP_409_CONFLICT


@pytest.mark.django_db
def test_delete_decision_environment_success(client: APIClient, init_db):
    obj_id = int(init_db.decision_environment.id)
    activation_id = int(init_db.activation.id)
    models.Activation.objects.filter(id=activation_id).delete()

    response = client.delete(f"{api_url_v1}/decision-environments/{obj_id}/")
    assert response.status_code == status.HTTP_204_NO_CONTENT

    assert models.DecisionEnvironment.objects.filter(pk=int(obj_id)).count() == 0


@pytest.mark.django_db
def test_delete_decision_environment_force(client: APIClient, init_db):
    obj_id = int(init_db.decision_environment.id)
    activation_id = int(init_db.activation.id)

    response = client.delete(f"{api_url_v1}/decision-environments/{obj_id}/?force=True")
    assert response.status_code == status.HTTP_204_NO_CONTENT

    assert models.DecisionEnvironment.objects.filter(pk=int(obj_id)).count() == 0
    activation = models.Activation.objects.get(pk=activation_id)
    assert activation.decision_environment is None


@pytest.fixture
def init_db():
    test_rulesets_sample = """
        ---
        - name: Test sample 001
        hosts: all
        sources:
            - ansible.eda.range:
                limit: 5
                delay: 1
            filters:
                - noop:
        rules:
            - name: r1
            condition: event.i == 1
            action:
                debug:
            - name: r2
            condition: event.i == 2
            action:
                debug:
        """.strip()

    project = models.Project.objects.create(
        name="test-project",
        description="Test Project",
        url="https://github.com/eda-project",
    )

    credential = models.Credential.objects.create(name="credential1", username="me", secret="sec1")

    decision_environment = models.DecisionEnvironment.objects.create(
        name="de1",
        image_url="registry.com/img1:tag1",
        credential=credential,
    )

    rulebook = models.Rulebook.objects.create(
        name="test-rulebook.yml",
        rulesets=test_rulesets_sample,
        project=project,
    )

    source_list = [
        {
            "name": "<unnamed>",
            "type": "range",
            "config": {"limit": 5},
            "source": "ansible.eda.range",
        }
    ]

    ruleset = models.Ruleset.objects.create(
        name="test-ruleset",
        sources=source_list,
        rulebook=rulebook,
    )

    rule = models.Rule.objects.create(
        name="say hello",
        action={"run_playbook": {"name": "ansible.eda.hello"}},
        ruleset=ruleset,
    )
    user = models.User.objects.create_user(
        username="luke.skywalker",
        first_name="Luke",
        last_name="Skywalker",
        email="luke.skywalker@example.com",
        password="secret",
    )
    activation = models.Activation.objects.create(
        name="test-activation",
        rulebook=rulebook,
        project=project,
        decision_environment=decision_environment,
        user=user,
    )

    activation_instance = models.ActivationInstance.objects.create(
        activation=activation,
    )

    return InitData(
        activation=activation,
        project=project,
        decision_environment=decision_environment,
        credential=credential,
        rulebook=rulebook,
        ruleset=ruleset,
        rule=rule,
        activation_instance=activation_instance,
    )
