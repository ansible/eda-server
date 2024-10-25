### Task Dispatcher

At demo phase currently, this removes use of Redis pub/sub queues in favor of pg_notify.
Logically, RQ worker is to be removed and replaced with in-house dispatcher library,
this library comes from AWX dispatcher.

#### Initial Phase, Task Trigger Demo

Have 2 terminal tabs open. It is suggested that you run in the worker container.

```
docker exec -it docker-eda-default-worker-1 /bin/bash
```

Now run the task runner in 1 of the 2 tabs.

```
aap-eda-manage run_worker_dispatcher
```

In the other tab, you need to do manual shell testing.

```
aap-eda-manage shell_plus
```

```python
from dispatcher.brokers.pg_notify import publish_message

publish_message("eda_workers", "aap_eda.tasks.orchestrator.monitor_rulebook_processes")
```

As an outcome of running this, you should see DEBUG level logs showing what happened in the 1st tab.

```
2024-10-25 18:34:16,951 dispatcher.brokers.pg_notify INFO     Set up pg_notify listening on channel 'eda_workers'
2024-10-25 18:34:16,951 dispatcher.brokers.pg_notify DEBUG    Starting listening for pg_notify notifications
2024-10-25 18:34:21,119 dispatcher.brokers.pg_notify DEBUG    Received notification: eda_workers - aap_eda.tasks.orchestrator.monitor_rulebook_processes
2024-10-25 18:34:21,119 dispatcher.producers.brokered INFO     Received message from channel 'eda_workers': aap_eda.tasks.orchestrator.monitor_rulebook_processes, sending to worker
2024-10-25 18:34:21,121 dispatcher.worker.task INFO     message to perform_work on {'task': 'aap_eda.tasks.orchestrator.monitor_rulebook_processes'}
2024-10-25 18:34:21,122 dispatcher.worker.task INFO     the type <class 'dict'>
2024-10-25 18:34:21,122 dispatcher.worker.task DEBUG    task <unknown> starting aap_eda.tasks.orchestrator.monitor_rulebook_processes(*[]) on worker 0
2024-10-25 18:34:21,163 dispatcher.pool DEBUG    Task completed by worker 0: None
```

#### Plugging in Schedules

The setting `CELERYBEAT_SCHEDULE` is replaced with `CELERYBEAT_SCHEDULE`,
reflecting patterns in RQ worker vs dispatcher.

#### Substutiting RQ Workers with Dispatchers

This phase will replace calls to RQ Worker, both on the producer and consumer sides,
with equivelent replacements via the dispatcher lib.

#### Task Modifications

Behaviorly, pg_notify will work differently than RQ.
Some changes to the tasks will be needed so that it doesn't error.
