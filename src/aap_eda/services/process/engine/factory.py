#  Copyright 2023 Red Hat, Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.


from django.conf import settings

import aap_eda.services.exceptions as exceptions

from .kubernetes import Engine as KubernetesEngine
from .podman import Engine as PodmanEngine


def new_container_engine(activation_id: str):
    """Activation service factory."""
    """Returns an activation object based on the deployment type"""
    # TODO: deployment type should not be plain strings
    if settings.DEPLOYMENT_TYPE == "podman":
        return PodmanEngine(activation_id)
    if settings.DEPLOYMENT_TYPE == "k8s":
        return KubernetesEngine(activation_id)
    raise exceptions.InvalidDeploymentTypeError("Wrong deployment type")
