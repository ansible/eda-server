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

import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Rulebook:
    data: str
    type: str = "Rulebook"

    def to_json(self):
        return json.dumps(asdict(self))


@dataclass(frozen=True)
class Inventory:
    data: str
    type: str = "Inventory"

    def to_json(self):
        return json.dumps(asdict(self))


@dataclass(frozen=True)
class ExtraVars:
    data: str
    type: str = "ExtraVars"

    def to_json(self):
        return json.dumps(asdict(self))


@dataclass(frozen=True)
class SSHPrivateKey:
    data: str
    type: str = "SSHPrivateKey"

    def to_json(self):
        return json.dumps(asdict(self))
