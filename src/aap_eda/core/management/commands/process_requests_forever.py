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

from aap_eda.tasks.orchestrator import _manage

import time


class Command(BaseCommand):
    help = "Processes user requests"

    def add_arguments(self, parser):
        parser.add_argument("worker")
        parser.add_argument("delay", type=int, default=10, nargs="?")

    def handle(self, *args, **options) -> None:
        worker = options["worker"]
        while True:
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
                    podman,
                    DBLogger,
                )
                if request['request'] == 'stop':
                    manager.stop()
                if request['request'] == 'delete':
                    manager.delete()
            time.sleep(options['delay'])
