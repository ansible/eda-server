from .factory import new_container_engine, ContainerEngine
import aap_eda.core.models as models


class ActivationManager:
    def __init__(
        self,
        db_instance: models.Activation,
        container_engine: ContainerEngine = new_container_engine(),
    ):
        self.db_instance = db_instance
        self.container_engine = container_engine

    def _set_status():
        pass

    def _get_status(self):
        db_status = None
        pod_state = self.container_engine.get_status()
        if db_status == pod_state:
            return ActivationStatus()

    def start(self):
        """Start an activation.

        Ensure that the activation meets all the requirements to start,
        otherwise raise ActivationStartError.
        Starts the activation in an idepotent way.
        """
        # Check for the right statuses
        # Check is_valid(activation)
        # Check for a container
        #

    def restart(self):
        pass

    def monitor(self):
        self.restart()

    def update_logs(self):
        pass
