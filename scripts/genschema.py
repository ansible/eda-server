"""Regenerate openapi.yaml from the current code using drf-spectacular."""

import os
import re

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "aap_eda.settings.default")
os.environ.setdefault("EDA_SECRET_KEY", "insecure-dev-key-for-schema-gen")

django.setup()

from django.core.management import call_command  # noqa: E402

call_command("spectacular", "--format", "openapi", "--file", "openapi.yaml")


def _stabilize_yaml(path):
    """Sort enum arrays for deterministic output.

    drf-spectacular may emit enum values in non-deterministic order due to
    Python set iteration. This post-processes the generated YAML to sort
    those blocks without disturbing the rest of the file formatting.
    """
    with open(path) as f:
        lines = f.readlines()

    # Sort YAML enum blocks: "enum:" followed by "- value" lines
    i = 0
    while i < len(lines):
        stripped = lines[i].rstrip()
        if stripped.endswith("enum:") and not stripped.endswith(
            "x-spec-enum-id:"
        ):
            j = i + 1
            enum_items = []
            while j < len(lines):
                line = lines[j]
                if line.rstrip() == "" or not line.lstrip().startswith("- "):
                    break
                enum_items.append(line)
                j += 1
            if enum_items:
                enum_items.sort()
                lines[i + 1 : j] = enum_items
                i = i + 1 + len(enum_items)
            else:
                i += 1
        else:
            i += 1

    # Sort description enum lines: "* `value` - label"
    # Each item may have indented continuation lines; keep them
    # attached to their bullet when sorting.
    enum_line_re = re.compile(r"^(\s+)\* `([^`]+)` - ")
    i = 0
    while i < len(lines):
        m = enum_line_re.match(lines[i])
        if m:
            indent = m.group(1)
            items = []
            j = i
            while j < len(lines):
                bm = enum_line_re.match(lines[j])
                if bm:
                    items.append([lines[j]])
                    j += 1
                    while j < len(lines) and not enum_line_re.match(lines[j]):
                        line = lines[j]
                        if line.strip() == "" or (
                            not line.startswith(indent + " ")
                            and not line.startswith(indent + "\t")
                        ):
                            break
                        items[-1].append(line)
                        j += 1
                else:
                    break
            if len(items) > 1:
                items.sort(
                    key=lambda item: enum_line_re.match(item[0]).group(2)
                )
                flat = [line for item in items for line in item]
                lines[i:j] = flat
            i += sum(len(item) for item in items)
        else:
            i += 1

    with open(path, "w") as f:
        f.writelines(lines)


_stabilize_yaml("openapi.yaml")
