#  Copyright 2022-2023 Red Hat, Inc.
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


import typing as tp

from django.db.models import QuerySet

from .activation import Activation
from .source import Source

ParentProcessType = tp.Union[Source, Activation]


# TODO(alex): So far this class implements methods on demand as
# they are needed. If it grows too much, it might be implemented
# in a smarter way, customizing the __getattr__ method to mimic
# the behavior of the django orm.
class CombinedQuerySet:
    """Combine two QuerySets into one."""

    def __init__(self, queryset1: QuerySet, queryset2: QuerySet):
        self.queryset1 = queryset1
        self.queryset2 = queryset2

    def __iter__(self) -> tp.Iterator[ParentProcessType]:
        for item in self.queryset1:
            yield item
        for item in self.queryset2:
            yield item

    def count(self) -> int:
        """Return the number of objects in the combined queryset."""
        return self.queryset1.count() + self.queryset2.count()


class ProcessParentProxy:
    """Proxy for Source and Activation models."""

    def __init__(self, model_instance: ParentProcessType):
        self.model_instance = model_instance
        self.is_activation = isinstance(model_instance, Activation)
        self.is_source = isinstance(model_instance, Source)

    def __getattr__(self, name: str):
        return getattr(self.model_instance, name)

    def __str__(self) -> str:
        return f"Process parent: {self.model_instance}, id: {self.id}"

    @property
    def instance(self) -> ParentProcessType:
        """Return the instance of the model."""
        return self.model_instance

    def to_dict(self) -> dict[str, tp.Any]:
        """Return a dictionary representation of the object.

        Used for serialization for redis rq tasks.
        """
        return {
            "id": self.id,
            "is_activation": self.is_activation,
            "is_source": self.is_source,
        }

    @staticmethod
    def from_dict(data: dict[str, tp.Any]) -> "ProcessParentProxy":
        """Return a ProcessParentProxy from a dictionary representation.

        Used for deserialization for redis rq tasks.
        """
        if data["is_activation"]:
            return ProcessParentProxy(Activation.objects.get(id=data["id"]))
        return ProcessParentProxy(Source.objects.get(id=data["id"]))

    @staticmethod
    def filter(**kwargs) -> CombinedQuerySet:  # noqa: A003
        """Filter Source and Activation objects."""
        return CombinedQuerySet(
            Source.objects.filter(**kwargs),
            Activation.objects.filter(**kwargs),
        )
