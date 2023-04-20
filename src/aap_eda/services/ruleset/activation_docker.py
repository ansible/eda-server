import logging

import docker

logger = logging.getLogger(__name__)


class ActivationDocker:
    def __init__(self, image_name: str):
        self.client = docker.from_env()
        self.image = self.client.images.pull(image_name)

    def run_container(self, cmd: list[str]):
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
