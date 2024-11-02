### Task Dispatcher

At demo phase currently, this removes use of Redis pub/sub queues in favor of pg_notify.
RQ worker is removed and replaced with in-house dispatcher library,
coming from the AWX dispatcher.

#### Initial Phase, Task Trigger Demo

Have 2 terminal tabs open. It is suggested that you run in the worker container.

```
docker exec -it docker-eda-default-worker-1 /bin/bash
```

Now run the task runner in 1 of the 2 tabs.

```
aap-eda-manage run_worker_dispatcher
```

In the other tab, you need to do manual testing with `aap-eda-manage shell`:

```python
from dispatcher.brokers.pg_notify import publish_message
publish_message("eda_workers", "aap_eda.tasks.orchestrator._manage")
```

As an outcome of running this, you should see DEBUG level logs showing what happened in the 1st tab.

```
2024-11-04 14:19:43,613 dispatcher.worker.task ERROR    Worker failed to run task aap_eda.tasks.orchestrator._manage(*[], **{}
Traceback (most recent call last):
  File "/app/src/dispatcher/dispatcher/worker/task.py", line 113, in perform_work
    result = self.run_callable(message)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/src/dispatcher/dispatcher/worker/task.py", line 87, in run_callable
    return _call(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^
TypeError: _manage() missing 2 required positional arguments: 'process_parent_type' and 'id'
```

These logs are telling you your call was incorrect.

#### Plugging in Schedules

The setting `RQ_PERIODIC_JOBS` is replaced with `CELERYBEAT_SCHEDULE`,
naming subject to revision.
This is the dispatcher naming for this.

#### Substutiting RQ Workers with Dispatchers

Commands that run `rqworker` are replaced with dispatcher commands in `tools/docker/docker-compose-dev.yaml`, for example.

#### Task Modifications

Behaviorly, pg_notify will work differently than RQ.
Some changes to the tasks are needed so that it doesn't error.
This is seen with the use of `advisory_lock`, for example.
