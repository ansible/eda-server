from django.core.management import BaseCommand, CommandError

import aap_eda.tasks.activation_request_queue as requests_queue
from aap_eda.core import models
from aap_eda.core.enums import (
    ActivationRequest,
    ActivationStatus,
    ProcessParentType,
)
from aap_eda.core.models import Activation, ActivationRequestQueue, EventStream
from aap_eda.core.tasking import unique_enqueue
from pprint import pprint

from aap_eda.services.activation.engine.podman import Engine as PodmanEngine
from aap_eda.services.activation.db_log_handler import DBLogger
from aap_eda.services.activation.manager import ActivationManager

from aap_eda.tasks.orchestrator import _manage, system_restart_activation


class Command(BaseCommand):
    help = "Runs the monitoring code"

    def add_arguments(self, parser):
        parser.add_argument("worker", nargs="?")

    def handle(self, *args, **options) -> None:
        worker = options.get("worker")
        if worker:
            my_activations = models.Activation.objects.filter(
                latest_instance__worker=worker
            )
            my_activation_ids = my_activations.values_list("id")
            requests = models.ActivationRequestQueue.objects.filter(
                process_parent_type="activation",
                process_parent_id__in=my_activation_ids,
            ).values()
            pprint(list(requests))
            for request in requests:
                podman = PodmanEngine(request["process_parent_id"])
                manager = ActivationManager(
                    models.Activation.objects.get(id=request["process_parent_id"]),
                    system_restart_activation,
                    podman,
                    DBLogger,
                )
                if request['request'] == 'stop':
                    manager.stop()
                if request['request'] == 'delete':
                    manager.delete()
                if request['request'] == 'restart':
                    manager.restart()
        else:
            for (
                request
            ) in models.ActivationRequestQueue.objects.all().values():
                print(request)
                #    _manage(request['process_parent_type'], request['process_parent_id'])
                if request["process_parent_type"] == "activation":
                    try:
                        act = models.Activation.objects.get(
                            id=request["process_parent_id"]
                        )
                        print(act.latest_instance.worker)
                    except models.Activation.DoesNotExist:
                        pass
