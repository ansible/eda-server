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


class SecretValue:
    __slots__ = ("_value",)

    def __init__(self, value):
        self._value = value

    def __str__(self):
        return "**********" if self._value else ""

    def __repr__(self):
        return f"{self.__class__.__name__}({self}))"

    def __len__(self):
        return len(self._value)

    def __hash__(self):
        return hash(self._value)

    def __eq__(self, other):
        if isinstance(other, SecretValue):
            other = other._value
        return self._value == other

    def get_secret_value(self) -> str:
        return self._value
