from aap_eda.core import models


def generate_simple_audit_log(
    action, resource_type, resource_name, organization
):
    log_msg = (
        f"Action: {action} / "
        f"ResourceType: {resource_type} / "
        f"ResourceName: {resource_name} / "
        f"Organization: {organization}"
    )
    return log_msg


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
