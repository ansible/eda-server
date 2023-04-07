import logging

import docker

logger = logging.getLogger(__name__)


class ActivationDockers:
    def __init__(self, image_name: str):
        self.client = docker.DockerClient(
            base_url="unix://var/run/docker.sock", version="auto"
        )
        self.image = self.client.images.pull(image_name)

    def create_container(self, url, activation_id):
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

        container = self.client.containers.create(
            image=self.image,
            command=cmd,
            environment=env,
            extra_hosts=extra_hosts,
            hostname="app-eda-host",
        )

        logger.info(
            f"Created container: name: {container.name}, "
            f"image: {container.image}, "
            f"command: {cmd}"
        )

        return container
