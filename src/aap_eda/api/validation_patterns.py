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

"""Inject DAB CleanTextMixin frontend patterns into OPTIONS metadata.

EDA defines its own ``DEFAULT_METADATA_CLASS``
(``aap_eda.api.metadata.EDAMetadata``) rather than using DAB's
``CleanTextMetadata``, so top-level CharField OPTIONS metadata is
not handled automatically by DAB --
``inject_top_level_clean_text_patterns`` is called from
``EDAMetadata.get_field_info`` to cover it.

JSON sub-keys (credential type inputs) are domain-owned schemas
that DAB has no visibility into at all, so pattern injection for
those lives here unconditionally.

Depends on django-ansible-base (AAP-85987) for
``build_tier2_frontend_pattern`` and ``inject_clean_text_patterns``.
Until that lands on DAB devel, injection is a no-op so EDA can
still import and run.
"""

import copy

from ansible_base.lib.utils.settings import get_setting

try:
    from ansible_base.lib.metadata import (
        build_tier2_frontend_pattern,
    )
except ImportError:  # pragma: no cover - DAB without AAP-85987
    build_tier2_frontend_pattern = None

try:
    from ansible_base.lib.metadata import (
        inject_clean_text_patterns as _dab_inject_clean_text_patterns,
    )
except ImportError:  # pragma: no cover - DAB without AAP-85987
    _dab_inject_clean_text_patterns = None

try:
    from ansible_base.lib.metadata import TIER2_PATTERN_DESCRIPTION
except ImportError:  # pragma: no cover - DAB without AAP-85987
    TIER2_PATTERN_DESCRIPTION = (
        "This field can't include HTML tags, script markup, "
        "unsafe URI schemes, shell or template syntax, "
        "or control characters."
    )

_STRING_TYPES = frozenset({"string", "str"})


def enhanced_input_validation_enabled():
    """Check if enhanced input validation is enabled."""
    return bool(get_setting("ENHANCED_INPUT_VALIDATION_ENABLED", False))


def free_text_pattern_metadata():
    """Return Tier 2 pattern keys for API clients, or ``None``."""
    if build_tier2_frontend_pattern is None:
        return None
    return {
        "pattern": build_tier2_frontend_pattern(),
        "pattern_description": TIER2_PATTERN_DESCRIPTION,
        "flags": "i",
    }


def inject_free_text_pattern(field_schema, *, secret=False):
    """Mutate *field_schema* in place for non-secret string fields.

    No-op when the install-time toggle is off or DAB pattern
    helpers are missing.
    """
    if not isinstance(field_schema, dict):
        return field_schema
    if not enhanced_input_validation_enabled():
        return field_schema
    if secret or field_schema.get("secret") is True:
        return field_schema
    field_type = field_schema.get("type", "string")
    if field_type not in _STRING_TYPES:
        return field_schema

    metadata = free_text_pattern_metadata()
    if metadata is None:
        return field_schema
    field_schema.update(metadata)
    return field_schema


def inject_patterns_into_field_list(fields):
    """Inject patterns into a credential-type ``fields`` list.

    Each field is shallow-copied before mutation so shared /
    module-level schema dicts are never modified.
    """
    if not enhanced_input_validation_enabled():
        return
    if not isinstance(fields, list):
        return
    for i, field in enumerate(fields):
        fields[i] = inject_free_text_pattern(copy.copy(field))


def inject_top_level_clean_text_patterns(field, field_info):
    """Advertise DAB CleanTextMixin patterns on a top-level field.

    Delegates entirely to DAB's ``inject_clean_text_patterns``,
    which no-ops unless ``ENHANCED_INPUT_VALIDATION_ENABLED`` is on
    and the field's serializer mixes in ``CleanTextMixin``.
    No-op when the DAB helper is missing.
    """
    if _dab_inject_clean_text_patterns is None:
        return field_info
    return _dab_inject_clean_text_patterns(field, field_info)
