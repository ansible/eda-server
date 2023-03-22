import time
from http import HTTPStatus

from eda_qa.api import get_api_client
from eda_qa.api.common import Response
from eda_qa.api.tasks import FINISHED_STATES
from eda_qa.config import config
from eda_qa.exceptions import HttpError

# TODO: wrong schema response
# use default client when https://issues.redhat.com/browse/AAP-9727 is fixed
FIXED_CLIENT = get_api_client()
FIXED_CLIENT.openapi_client.configuration.discard_unknown_keys = True


def wait_for_task(
    task_id: str, timeout: float = config.default_task_timeout, check_interval: float = 0.5
) -> Response:
    """
    Receive a task_id and wait for it to finish in the given timeout.
    """
    start = time.time()
    while time.time() - start < timeout:
        task_response = FIXED_CLIENT.tasks.read(task_id)
        if task_response.status_code != HTTPStatus.OK:
            raise HttpError(f"Error fetching task {task_id}: {task_response.data}")
        if task_response.data.status in FINISHED_STATES:
            return task_response
        time.sleep(check_interval)
    else:
        raise TimeoutError(f"Task {task_id} did not finish in {timeout} seconds")
