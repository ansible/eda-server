import time
from datetime import timedelta

from django.core.management import BaseCommand
from django.utils import timezone

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus
from aap_eda.core.models import ActivationRequestQueue
from aap_eda.core.models.rulebook_process import RulebookProcess
from aap_eda.services.activation.db_log_handler import DBLogger
from aap_eda.services.activation.engine.podman import Engine as PodmanEngine
from aap_eda.services.activation.manager import ActivationManager
from aap_eda.tasks.orchestrator import system_restart_activation


class Command(BaseCommand):
    help = "Runs the monitoring code"

    def add_arguments(self, parser):
        parser.add_argument("worker", type=str)
        parser.add_argument("delay", type=int, default=60, nargs="?")

    def handle(self, *args, **options) -> None:
        worker = options["worker"]
        while True:
            self.monitor(worker)
            self.process_requests(worker)
            self.find_lost_activations()
            time.sleep(options["delay"])

    def monitor(self, worker):
        q = models.RulebookProcess.objects.filter(
            status=ActivationStatus.RUNNING, worker=worker
        )
        for process in q.values():
            podman = PodmanEngine(process["activation_id"])
            manager = ActivationManager(
                models.Activation.objects.get(id=process["activation_id"]),
                system_restart_activation,
                podman,
                DBLogger,
            )
            manager.monitor()

    def process_requests(self, worker):
        my_activations = models.Activation.objects.filter(
            latest_instance__worker=worker
        )
        my_activation_ids = my_activations.values_list("id")
        requests = models.ActivationRequestQueue.objects.filter(
            process_parent_type="activation",
            process_parent_id__in=my_activation_ids,
        ).values()
        for request in list(requests):
            podman = PodmanEngine(request["process_parent_id"])
            manager = ActivationManager(
                models.Activation.objects.get(id=request["process_parent_id"]),
                system_restart_activation,
                podman,
                DBLogger,
            )
            if request["request"] == "stop":
                manager.stop()
                ActivationRequestQueue.objects.filter(
                    id=request["id"]
                ).delete()
            if request["request"] == "delete":
                manager.delete()
                ActivationRequestQueue.objects.filter(
                    id=request["id"]
                ).delete()
            if request["request"] == "restart":
                manager.restart()
                ActivationRequestQueue.objects.filter(
                    id=request["id"]
                ).delete()

    def find_lost_activations(self):
        lost_processes = RulebookProcess.objects.filter(
            status="running",
            updated_at__lte=timezone.now() - timedelta(seconds=600),
        ).values()
        for process in lost_processes:
            podman = PodmanEngine(process["activation_id"])
            manager = ActivationManager(
                models.Activation.objects.get(id=process["activation_id"]),
                system_restart_activation,
                podman,
                DBLogger,
            )
            manager._unresponsive_policy()
