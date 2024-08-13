from aap_eda.core import models


def get_credential_name_from_data(data):
    credential_name = ""
    if data.data["eda_credential_id"]:
        credential_name = (
            models.EdaCredential.objects.get(
                pk=data.data["eda_credential_id"]
            ).name
            if data.data["eda_credential_id"]
            else None
        )
    return credential_name


def get_organization_name_from_data(data):
    org_name = ""
    if data.data["organization_id"]:
        org_name = (
            models.Organization.objects.get(
                pk=data.data["organization_id"]
            ).name
            if data.data["organization_id"]
            else None
        )
    return org_name


def get_project_name_from_id(id):
    project = models.Project.objects.get(pk=id).name
    return project


def get_rulebook_name_from_id(id):
    rulebook = models.Rulebook.objects.get(pk=id).name
    return rulebook


def get_de_name_from_id(id):
    rulebook = models.DecisionEnvironment.objects.get(pk=id).name
    return rulebook
