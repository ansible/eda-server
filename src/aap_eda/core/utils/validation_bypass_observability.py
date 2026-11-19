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

"""Register django-ansible-base ORM bypass observability for EDA.

See DAB ``docs/lib/validation_bypass_observability.md``. EDA's production
``QuerySet.update()`` hook for registered text is project import
(``audited_queryset_update`` on ``Activation.rulebook_rulesets``).
"""

from ansible_base.lib.utils.validation_signals import (
    extend_caller_allowlist_prefixes,
    extend_internal_caller_prefixes,
    register_validation_signals,
)


def configure_validation_bypass_observability() -> None:
    """Call from ``CoreConfig.ready()`` after DAB is installed."""
    register_validation_signals()
    extend_caller_allowlist_prefixes(
        [
            "aap_eda.api.views",
            "aap_eda.services.project",
            "aap_eda.services",
            "aap_eda.tasks",
            "aap_eda.management",
        ]
    )
    extend_internal_caller_prefixes(
        [
            "aap_eda.core.models",
            "aap_eda.core.utils.validation_bypass_observability",
            "aap_eda.services.project.imports",
        ]
    )
