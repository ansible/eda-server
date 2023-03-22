"""
utils for eda projects
"""
import time
from http import HTTPStatus
from urllib.parse import urlparse

from eda_qa.api import api_client
from eda_qa.api.common import Response
from eda_qa.api.projects import ProjectImportStates
from eda_qa.config import config
from eda_qa.exceptions import HttpError
from eda_qa.exceptions import ProjectImportFailed
from eda_qa.utils import http_client


def wait_for_project_import(
    project_id: int,
    timeout: float = config.default_timeout,
    check_interval: float = 0.5,
) -> Response:
    """
    Receive a project ID and wait for the project import state
    to reach completed status. Return the project response.
    """
    start = time.time()
    while time.time() - start < timeout:
        project_response = api_client.projects.read(project_id)
        if project_response.status_code != HTTPStatus.OK:
            raise HttpError(f"Error fetching project ID {project_id}: {project_response.data}")
        if project_response.data.import_state == ProjectImportStates.FAILED:
            raise ProjectImportFailed(
                f"Failed to import project ID {project_id}: {project_response.data}"
            )
        if project_response.data.import_state == ProjectImportStates.COMPLETED:
            return project_response
        time.sleep(check_interval)
    else:
        raise TimeoutError(f"Project ID {project_id} did not finish in {timeout} seconds")


def get_project_file(filepath: str) -> bytes:
    """
    Fetch a file from the default project repository.
    Assumes that the repository is in github and the branch in main
    Receives a string with the filepath of the file in the project root.
    Returns the bytes content of the file.
    """

    base_url = urlparse(config.default_project_url)._replace(netloc="raw.githubusercontent.com")
    url = "/".join([base_url.geturl(), "main", filepath])

    response = http_client.get(url)

    if response.status_code != 200:
        raise Exception(f"Error requesting {url}, {response.status_code} {response.content}")

    return response.content
