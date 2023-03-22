import typing

import nanoid

import eda_api.apis as apis
from eda_qa.api.common import BaseApi
from eda_qa.api.common import CaseInsensitiveString
from eda_qa.api.common import Response
from eda_qa.config import config


class ProjectsApi(BaseApi):
    """
    Wraps the openapi api for projects endpoints
    """

    api = apis.ProjectsApi

    def list(  # noqa: A003
        self,
        name: str = None,
        page: int = 1,
        page_size: int = None,
        url: str = None,
    ) -> Response:
        """
        List projects
        """
        operation = "projects_list"

        payload = {}

        if name is not None:
            payload["name"] = name
        if page_size is not None:
            payload["page_size"] = page_size
        if url is not None:
            payload["url"] = url

        payload["page"] = page

        return self.run(operation, **payload)

    def read(self, project_id: int, **kwargs) -> Response:
        """
        Retrieves a project
        """
        operation = "projects_retrieve"
        return self.run(operation, project_id, **kwargs)

    def create(
        self,
        name: typing.Optional[str] = None,
        description: typing.Optional[str] = None,
        url: typing.Optional[str] = None,
        **kwargs,
    ) -> Response:
        """
        Creates a project
        """
        operation = "projects_create"

        if name is None:
            name = f"QE-project-{nanoid.generate()}"
        if description is None:
            description = "Sample project created by QE test suite"
        if url is None:
            url = config.default_project_url  # type: ignore comment;

        payload = {"name": name, "description": description, "url": url}

        return self.run(operation, payload, **kwargs)

    def delete(self, project_id: int, **kwargs) -> Response:
        """
        Deletes a project
        """
        operation = "projects_destroy"

        return self.run(operation, project_id, **kwargs)

    def update(
        self,
        project_id: int,
        name: typing.Optional[str] = None,
        description: typing.Optional[str] = None,
        **kwargs,
    ):
        """
        Updates a project
        """
        operation = "projects_partial_update"

        payload = {}

        if name is not None:
            payload["name"] = name
        if description is not None:
            payload["description"] = description

        return self.run(operation, project_id, patched_project=payload, **kwargs)


class ProjectImportStates:
    COMPLETED = CaseInsensitiveString("completed")
    FAILED = CaseInsensitiveString("failed")
    PENDING = CaseInsensitiveString("pending")
    RUNNING = CaseInsensitiveString("running")
