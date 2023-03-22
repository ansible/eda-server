"""
rules api
"""
import eda_api.apis as apis
from eda_qa.api.common import BaseApi
from eda_qa.api.common import CaseInsensitiveString
from eda_qa.api.common import Response


class TasksApi(BaseApi):
    """
    Wraps the openapi api for tasks endpoints
    """

    api = apis.TasksApi

    def list(self, *args, **kwargs) -> Response:  # noqa: A003
        operation = "tasks_list"
        return self.run(operation, *args, **kwargs)

    def read(self, task_id: str, *args, **kwargs):
        operation = "tasks_retrieve"
        return self.run(operation, id=task_id, *args, **kwargs)


class TaskStates:
    QUEUED = CaseInsensitiveString("queued")
    FINISHED = CaseInsensitiveString("finished")
    FAILED = CaseInsensitiveString("failed")
    STARTED = CaseInsensitiveString("started")
    DEFERRED = CaseInsensitiveString("deferred")
    SCHEDULED = CaseInsensitiveString("scheduled")
    STOPPED = CaseInsensitiveString("stopped")
    CANCELED = CaseInsensitiveString("canceled")


FINISHED_STATES = [TaskStates.FINISHED, TaskStates.FAILED, TaskStates.STOPPED, TaskStates.CANCELED]
