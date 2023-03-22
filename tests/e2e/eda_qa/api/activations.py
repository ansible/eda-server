import typing

import nanoid

import eda_api.apis as apis
from eda_qa.api.common import BaseApi
from eda_qa.api.common import Response


class RestartPolicy:
    ON_FAILURE = "on-failure"
    ALWAYS = "always"
    NEVER = "never"


class ActivationsApi(BaseApi):
    """
    Wraps the openapi api for inventories endpoint
    """

    api = apis.ActivationsApi

    def read(self, activation_id: int, **kwargs) -> Response:
        """
        Retrieves an activation
        """
        operation = "activations_retrieve"
        return self.run(operation, activation_id, **kwargs)

    def create(
        self,
        name: typing.Optional[str] = None,
        rulebook_id: typing.Optional[int] = None,
        inventory_id: typing.Optional[int] = None,
        description: typing.Optional[str] = None,
        restart_policy: typing.Optional[str] = None,
        is_enabled: typing.Optional[bool] = None,
        extra_var_id: typing.Optional[int] = None,
        execution_environment: typing.Optional[str] = None,
        working_directory: typing.Optional[str] = None,
        **kwargs,
    ) -> Response:
        """
        Create an activation
        """
        operation = "activations_create"

        if name is None:
            name = f"QE-activation-{nanoid.generate()}"
        if description is None:
            description = "Sample project created by QE test suite"
        if rulebook_id is None:
            rulebook_id = self.api_client.rulebooks.get_default_rulebook()["id"]
        if inventory_id is None:
            inventory_id = self.api_client.inventories.get_default_inventory()["id"]

        payload = {
            "name": name,
            "description": description,
            "rulebook_id": rulebook_id,
            "inventory_id": inventory_id,
        }

        if extra_var_id is not None:
            payload["extra_var_id"] = extra_var_id
        if restart_policy is not None:
            payload["restart_policy"] = restart_policy
        if is_enabled is not None:
            payload["is_enabled"] = is_enabled
        if execution_environment is not None:
            payload["execution_environment"] = execution_environment
        if working_directory is not None:
            payload["working_directory"] = working_directory

        return self.run(operation, payload, **kwargs)
