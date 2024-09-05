#  Copyright 2024 Red Hat, Inc.
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

from aap_eda.api import exceptions as api_exc
from aap_eda.core import models


class SharedResourceSerializerMixin:
    def validate_shared_resource(self, data=None):
        if not settings.ALLOW_LOCAL_RESOURCE_MANAGEMENT:
            view = self.context.get("view")
            action = view.action.capitalize() if view else "action"

            # exception where we should allow updating is_superuser field
            if action == "Partial_update" and isinstance(
                view.get_object(), models.User
            ):
                if data and "is_superuser" in data:
                    return {"is_superuser": data["is_superuser"]}

            raise api_exc.Forbidden(
                f"{action} should be done through the platform ingress"
            )
