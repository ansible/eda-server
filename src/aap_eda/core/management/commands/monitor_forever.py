import time

from django.core.management import BaseCommand

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus
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
            time.sleep(options["delay"])
