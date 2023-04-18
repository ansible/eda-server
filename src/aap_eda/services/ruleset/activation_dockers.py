import logging

import docker
from django.conf import settings

logger = logging.getLogger(__name__)


class ActivationDockers:
    def __init__(self, image_name: str):
        self.client = docker.DockerClient(
            base_url=settings.EDA_DOCKER_SOCKET_PATH, version="auto"
        )
        self.image = self.client.images.pull(image_name)

    def run_container(self, url, activation_id):
        cmd = [
            "ansible-rulebook",
            "--worker",
            "--websocket-address",
            url,
            "--id",
            str(activation_id),
        ]

        env = ["ANSIBLE_FORCE_COLOR=True"]
        extra_hosts = ("host.docker.internal:host-gateway",)

        container = self.client.containers.run(
            image=self.image,
            command=cmd,
            stdout=True,
            stderr=True,
            remove=True,
            detach=True,
            environment=env,
            extra_hosts=extra_hosts,
        )

        logger.info(
            f"Created container: name: {container.name}, "
            f"image: {container.image}, "
            f"command: {cmd}"
        )

        return container
