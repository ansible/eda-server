import time
from concurrent.futures import ThreadPoolExecutor, wait
from threading import Lock
from unittest import mock

import pytest

from tests.integration.utils import ThreadSafeList


@pytest.mark.parametrize(
    "module_data",
    [
        {
            "module_path": "aap_eda.tasks.analytics",
            "fn_mock": "_gather_analytics",
            "fn_call": "gather_analytics",
            "fn_args": [],
        },
        {
            "module_path": "aap_eda.tasks.orchestrator",
            "fn_mock": "monitor_rulebook_processes_no_lock",
            "fn_call": "monitor_rulebook_processes",
            "fn_args": [],
        },
        {
            "module_path": "aap_eda.tasks.project",
            "fn_mock": "_import_project",
            "fn_call": "import_project",
            "fn_args": [1],
        },
        {
            "module_path": "aap_eda.tasks.project",
            "fn_mock": "_sync_project",
            "fn_call": "sync_project",
            "fn_args": [1],
        },
        {
            "module_path": "aap_eda.tasks.project",
            "fn_mock": "_monitor_project_tasks",
            "fn_call": "monitor_project_tasks",
            "fn_args": [],
        },
    ],
    ids=[
        "gather_analytics",
        "monitor_rulebook_processes",
        "import_project",
        "sync_project",
        "monitor_project_tasks",
    ],
)
@pytest.mark.django_db
def test_job_uniqueness(module_data):
    call_log = []
    lock = Lock()

    def gather_analytics_wrapper_call(shared_list):
        """Patch _gather_analytics in a thread-safe way inside each thread."""
        import importlib

        module = importlib.import_module(module_data["module_path"])

        importlib.reload(module)

        with mock.patch(
            f"{module_data['module_path']}.{module_data['fn_mock']}",
        ) as fn_mock:

            def record_call(void=None):
                time.sleep(1)
                shared_list.append("called")

            fn_mock.side_effect = record_call
            getattr(module, module_data["fn_call"])(*module_data["fn_args"])

    def thread_safe_call():
        gather_analytics_wrapper_call(ThreadSafeList(call_log, lock))

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(thread_safe_call),
            executor.submit(thread_safe_call),
        ]
        wait(futures, timeout=3)

    assert len(call_log) == 1
