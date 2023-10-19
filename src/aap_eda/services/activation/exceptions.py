#  Copyright 2023 Red Hat, Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0pass
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.


class ActivationException(Exception):
    pass


class ActivationStartError(Exception):
    pass


class K8sActivationException(ActivationException):
    pass


class DeactivationException(ActivationException):
    pass


class ActivationRecordNotFound(ActivationException):
    pass


class ActivationPodNotFound(ActivationException):
    pass


class ActivationImagePullError(ActivationException):
    pass


class ActivationImageNotFound(ActivationException):
    pass
