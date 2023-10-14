from django.conf import settings

import aap_eda.services.exceptions as exceptions

from .kubernetes import Engine as KubernetesEngine
from .podman import Engine as PodmanEngine


def new_container_engine():
    """Activation service factory."""
    """Returns an activation object based on the deployment type"""
    # TODO: deployment type should not be plain strings
    if settings.DEPLOYMENT_TYPE == "podman":
        return PodmanEngine()
    if settings.DEPLOYMENT_TYPE == "k8s":
        return KubernetesEngine()
    raise exceptions.InvalidDeploymentTypeError("Wrong deployment type")
