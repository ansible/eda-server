import importlib
import time
from concurrent.futures import ThreadPoolExecutor, wait
from contextlib import ExitStack
from threading import Lock
from unittest import mock

import pytest


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
            "fn_mock": "_monitor_project_tasks",
            "fn_call": "monitor_project_tasks",
            "fn_args": [],
        },
        {
            "module_path": "aap_eda.tasks.project",
            "fn_mock": "_import_project_no_lock",
            "fn_call": "_import_project",
            "fn_args": [1],
        },
        {
            "module_path": "aap_eda.tasks.project",
            "fn_mock": "_sync_project_no_lock",
            "fn_call": "_sync_project",
            "fn_args": [1],
        },
        {
            "module_path": "aap_eda.tasks.management",
            "fn_mock": "call_command",
            "fn_call": "_aap_eda_manage",
            "fn_args": ["parallel-job", "test_management_command", {}],
        },
    ],
    ids=[
        "gather_analytics",
        "monitor_rulebook_processes",
        "monitor_project_tasks",
        "_import_project",
        "_sync_project",
        "_aap_eda_manage",
    ],
)
@pytest.mark.django_db
@pytest.mark.multithreaded
def test_job_uniqueness(module_data):
    call_log = []
    lock = Lock()
    module = importlib.import_module(module_data["module_path"])
    importlib.reload(module)

    patches = [
        mock.patch(
            f"{module_data['module_path']}.{module_data['fn_mock']}",
        ),
    ]

    # Add mock for get_insights_tracking_state for analytics tests
    if module_data["fn_call"] == "gather_analytics":
        patches.append(
            mock.patch(
                "aap_eda.analytics.utils.get_insights_tracking_state",
                return_value=True,
            )
        )

    def thread_safe_call():
        try:
            getattr(module, module_data["fn_call"])(
                *module_data["fn_args"],
            )
        except Exception as e:
            pytest.fail(f"Exception raised in {module_data['fn_call']}: {e}")

    # Patch once, outside the worker threads. Patching inside each thread
    # races: the first thread to leave its ExitStack restores the original
    # attribute and clobbers the mock the other thread still relies on, so
    # neither call reaches the side effect and the assertion below sees 0.
    with ExitStack() as stack:
        mocks = [stack.enter_context(patch) for patch in patches]
        fn_mock = mocks[0]

        def record_call(void=None, **kwargs):
            time.sleep(1)
            with lock:
                call_log.append("called")

        fn_mock.side_effect = record_call

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(thread_safe_call),
                executor.submit(thread_safe_call),
            ]
            wait(futures, timeout=3)

    assert len(call_log) == 1
