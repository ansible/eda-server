#  Copyright 2025 Red Hat, Inc.
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

import yaml


class UnsafeString(str):
    pass


def unsafe_string_representer(
    dumper: yaml.SafeDumper, obj: UnsafeString
) -> yaml.ScalarNode:
    return dumper.represent_scalar("!unsafe", obj)


def get_dumper() -> yaml.SafeDumper:
    """Add representers to a YAML seriailizer."""
    safe_dumper = yaml.SafeDumper
    safe_dumper.add_representer(UnsafeString, unsafe_string_representer)
    return safe_dumper


def dump(filename: str, data: dict) -> None:
    """Write data to a file as YAML with unsafe strings."""
    if not isinstance(data, dict):
        raise TypeError("Data must be a dictionary")

    def transform_strings(data):
        """Recursively transform any string type to UnsafeString."""
        if isinstance(data, str):
            return UnsafeString(data)
        if isinstance(data, dict):
            return {k: transform_strings(v) for k, v in data.items()}
        if isinstance(data, list):
            return [transform_strings(v) for v in data]
        if isinstance(data, tuple):
            return tuple(transform_strings(v) for v in data)
        if isinstance(data, set):
            return {transform_strings(v) for v in data}
        return data

    data = transform_strings(data)

    with open(filename, "w") as f:
        yaml.dump(data, f, Dumper=get_dumper())
