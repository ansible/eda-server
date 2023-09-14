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

from django.core.exceptions import FieldDoesNotExist


class ModifiedAtUpdaterMixin:
    """Mixin to ensure that the `modified_at` field is updated.

    Ensure that the `modified_at` field is updated when the model
    is saved with specific fields (`update_fields`) specified for update.
    Only works for `auto_now` fields.
    """

    def save(self, *args, **kwargs):
        try:
            field = self._meta.get_field("modified_at")
        except FieldDoesNotExist:
            field = None
        if (
            field is not None
            and hasattr(field, "auto_now")
            and field.auto_now
            and kwargs.get("update_fields", [])
        ):
            kwargs["update_fields"].append("modified_at")
        super().save(*args, **kwargs)
