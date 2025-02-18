#  Copyright 2024 Red Hat, Inc.
# Licensed under the Apache License, Version 2.0 (the "License");
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

import logging
import os
import platform
import uuid
from collections import Counter
from datetime import datetime
from typing import Any, Generator, List, Optional, Tuple

import distro
import yaml
from ansible_base.resource_registry.models.service_identifier import service_id
from django.conf import settings
from django.db import DatabaseError, connection
from django.db.models import (
    Case,
    Count,
    DateTimeField,
    F,
    IntegerField,
    Manager,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from insights_analytics_collector import CsvFileSplitter, register

from aap_eda.analytics.utils import (
    collect_controllers_info,
    extract_job_details,
)
from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus
from aap_eda.core.exceptions import ParseError
from aap_eda.utils import get_eda_version

logger = logging.getLogger("aap_eda.analytics")

SOURCE_RESERVED_KEYS = ["name", "filters"]


@register(
    "config",
    "1.0",
    description="General platform configuration.",
    config=True,
)
def config(**kwargs) -> dict:
    os_info = f"{distro.name(pretty=True)} {distro.version(pretty=True)}"
    install_type = "traditional"
    if os.environ.get("container") == "oci":
        install_type = "openshift"
    elif "KUBERNETES_SERVICE_PORT" in os.environ:
        install_type = "k8s"
    return {
        "install_uuid": service_id(),
        "platform": {
            "system": platform.system(),
            "dist": os_info,
            "release": platform.release(),
            "type": install_type,
        },
        # skip license related info so far
        "eda_log_level": settings.APP_LOG_LEVEL,
        "eda_version": get_eda_version(),
    }


@register(
    "jobs_stats",
    "1.0",
    description="Stats data for jobs",
)
def jobs_stats(since: datetime, full_path: str, until: datetime, **kwargs):
    stats = {}
    audit_actions = _get_audit_action_qs(since, until)

    if not bool(audit_actions):
        return stats

    controllers = collect_controllers_info()
    for action in audit_actions.all():
        job_type, job_id, install_uuid = extract_job_details(
            action.url, controllers
        )
        if not job_type:
            continue

        data = stats.get(job_id, [])
        job_stat = {}
        job_stat["job_id"] = job_id
        job_stat["type"] = job_type
        job_stat["created_at"] = action.fired_at.strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        job_stat["status"] = action.status
        job_stat["url"] = action.url
        job_stat["install_uuid"] = install_uuid
        data.append(job_stat)

        stats[job_id] = data

    return stats


@register(
    "activations_stats",
    "1.0",
    format="csv",
    description="Stats for activations",
)
def activations_stats(
    since: datetime, full_path: str, until: datetime, **kwargs
) -> list[str]:
    has_ended_at_states = [
        ActivationStatus.FAILED.value,
        ActivationStatus.STOPPED.value,
        ActivationStatus.COMPLETED.value,
        ActivationStatus.UNRESPONSIVE.value,
        ActivationStatus.ERROR.value,
        ActivationStatus.WORKERS_OFFLINE.value,
    ]
    counts_query = (
        models.RulebookProcess.objects.filter(activation_id=OuterRef("pk"))
        .values("activation_id")
        .annotate(counts=Count("id"))
        .values("counts")
    )

    activations = (
        models.Activation.objects.annotate(
            ended_at=Case(
                When(status__in=has_ended_at_states, then=F("modified_at")),
                output_field=DateTimeField(),
            ),
            activations_counts=Coalesce(Subquery(counts_query), Value(0)),
            max_restart_count=Value(
                int(settings.ACTIVATION_MAX_RESTARTS_ON_FAILURE),
                output_field=IntegerField(),
            ),
        )
        .filter(
            Q(created_at__gt=since, created_at__lte=until)
            | Q(modified_at__gt=since, modified_at__lte=until)
        )
        .distinct()
    ).values(
        "id",
        "name",
        "status",
        "restart_count",
        "failure_count",
        "log_level",
        "organization_id",
        "created_at",
        "ended_at",
        "activations_counts",
        "max_restart_count",
    )

    return _copy_table("activations_stats", activations, full_path)


@register(
    "activations_table",
    "1.0",
    format="csv",
    description="Data on activations",
)
def activations_table(
    since: datetime, full_path: str, until: datetime, **kwargs
) -> list[str]:
    queryset = _get_query(models.Activation.objects, since, until).values(
        "id",
        "organization_id",
        "name",
        "description",
        "is_enabled",
        "git_hash",
        "decision_environment_id",
        "project_id",
        "rulebook_id",
        "extra_var",
        "restart_policy",
        "status",
        "current_job_id",
        "restart_count",
        "failure_count",
        "is_valid",
        "rulebook_name",
        "rulebook_rulesets",
        "ruleset_stats",
        "created_at",
        "modified_at",
        "status_updated_at",
        "status_message",
        "latest_instance_id",
        "log_level",
        "eda_system_vault_credential_id",
        "k8s_service_name",
        "source_mappings",
        "skip_audit_events",
    )

    return _copy_table("activations", queryset, full_path)


@register(
    "audit_actions_table",
    "1.0",
    format="csv",
    description="Data on audit_actions",
)
def audit_actions_table(
    since: datetime, full_path: str, until: datetime, **kwargs
) -> list[str]:
    audit_actions = _get_audit_action_qs(since, until)

    if not audit_actions.exists():
        return []

    return _copy_table("audit_actions", audit_actions, full_path)


@register(
    "audit_events_table",
    "1.0",
    format="csv",
    description="Data on audit_events",
)
def audit_events_table(
    since: datetime, full_path: str, until: datetime, **kwargs
) -> list[str]:
    audit_actions = _get_audit_action_qs(since, until)
    if not audit_actions.exists():
        return []

    audit_event_query = _get_audit_event_query(audit_actions).values(
        "id",
        "source_name",
        "source_type",
        "received_at",
        "rule_fired_at",
    )
    if not audit_event_query.exists():
        return []

    return _copy_table("audit_events", audit_event_query, full_path)


@register(
    "audit_rules_table",
    "1.0",
    format="csv",
    description="Data on audit_rules",
)
def audit_rules_table(
    since: datetime, full_path: str, until: datetime, **kwargs
) -> list[str]:
    audit_rules = _get_audit_rule_qs(since, until).values(
        "id",
        "organization_id",
        "name",
        "status",
        "created_at",
        "fired_at",
        "rule_uuid",
        "ruleset_uuid",
        "ruleset_name",
        "job_instance_id",
        "activation_instance_id",
    )
    if not audit_rules.exists():
        return []

    return _copy_table("audit_rules", audit_rules, full_path)


@register(
    "eda_credentials_table",
    "1.0",
    format="csv",
    description="Data on eda_credentials",
)
def eda_credentials_table(
    since: datetime, full_path: str, until: datetime, **kwargs
) -> list[str]:
    queryset = _get_query(models.EdaCredential.objects, since, until).values(
        "id",
        "organization_id",
        "name",
        "description",
        "managed",
        "created_at",
        "modified_at",
        "credential_type_id",
    )

    return _copy_table("eda_credentials", queryset, full_path)


@register(
    "credential_types_table",
    "1.0",
    format="csv",
    description="Data on credential_types",
)
def credential_types_table(
    since: datetime, full_path: str, until: datetime, **kwargs
) -> list[str]:
    queryset = _get_query(models.CredentialType.objects, since, until)

    return _copy_table("credential_types", queryset, full_path)


@register(
    "decision_environments_table",
    "1.0",
    format="csv",
    description="Data on decision_environments",
)
def decision_environments_table(
    since: datetime, full_path: str, until: datetime, **kwargs
) -> list[str]:
    queryset = _get_query(
        models.DecisionEnvironment.objects, since, until
    ).values(
        "id",
        "organization_id",
        "name",
        "description",
        "image_url",
        "eda_credential_id",
        "created_at",
        "modified_at",
    )

    return _copy_table("decision_environments", queryset, full_path)


@register(
    "event_streams_table",
    "1.0",
    format="csv",
    description="Data on event_streams",
)
def event_streams_table(
    since: datetime, full_path: str, until: datetime, **kwargs
) -> list[str]:
    event_streams = (
        models.EventStream.objects.filter(
            Q(created_at__gt=since, created_at__lte=until)
            | Q(modified_at__gt=since, modified_at__lte=until)
        )
        .order_by("id")
        .distinct()
    ).values(
        "id",
        "organization_id",
        "name",
        "event_stream_type",
        "eda_credential_id",
        "uuid",
        "created_at",
        "modified_at",
        "events_received",
        "last_event_received_at",
    )

    return _copy_table("event_streams", event_streams, full_path)


@register(
    "event_streams_by_activation_table",
    "1.0",
    format="csv",
    description="Data on event_streams used by each activation",
)
def event_streams_by_activation_table(
    since: datetime, full_path: str, until: datetime, **kwargs
) -> list[str]:
    activations = models.Activation.objects.filter(
        Q(created_at__gt=since, created_at__lte=until)
        | Q(modified_at__gt=since, modified_at__lte=until)
    ).distinct()

    event_streams = models.EventStream.objects.none()
    for activation in activations:
        event_streams |= activation.event_streams.all()

    if not bool(event_streams):
        return event_streams

    event_streams = event_streams.annotate(
        event_stream_id=F("id"),
        activation_id=F("activations__id"),
    ).values(
        "name",
        "event_stream_type",
        "eda_credential_id",
        "events_received",
        "last_event_received_at",
        "organization_id",
        "event_stream_id",
        "activation_id",
    )

    return _copy_table("event_streams_by_activation", event_streams, full_path)


@register(
    "event_streams_by_running_activations_table",
    "1.0",
    format="csv",
    description="Data on event_streams used by each running activation",
)
def event_streams_by_running_activations_table(
    since: datetime, full_path: str, until: datetime, **kwargs
) -> list[str]:
    running_states = [
        ActivationStatus.RUNNING,
        ActivationStatus.STARTING,
        ActivationStatus.PENDING,
    ]
    activations = (
        models.Activation.objects.filter(
            Q(created_at__gt=since, created_at__lte=until)
            | Q(modified_at__gt=since, modified_at__lte=until)
        )
        .filter(status__in=running_states)
        .distinct()
    )

    event_streams = models.EventStream.objects.none()
    for activation in activations:
        event_streams |= activation.event_streams.all()

    if not bool(event_streams):
        return models.EventStream.objects.none()

    event_streams = event_streams.annotate(
        event_stream_id=F("id"),
        activation_id=F("activations__id"),
    ).values(
        "name",
        "event_stream_type",
        "eda_credential_id",
        "events_received",
        "last_event_received_at",
        "organization_id",
        "event_stream_id",
        "activation_id",
    )

    return _copy_table(
        "event_streams_by_running_activations", event_streams, full_path
    )


@register(
    "projects_table",
    "1.0",
    format="csv",
    description="Data on projects",
)
def projects_table(
    since: datetime, full_path: str, until: datetime, **kwargs
) -> list[str]:
    queryset = _get_query(models.Project.objects, since, until).values(
        "id",
        "organization_id",
        "name",
        "description",
        "url",
        "proxy",
        "git_hash",
        "verify_ssl",
        "eda_credential_id",
        "archive_file",
        "import_state",
        "import_task_id",
        "import_error",
        "created_at",
        "modified_at",
        "scm_type",
        "scm_branch",
        "scm_refspec",
        "signature_validation_credential_id",
    )

    return _copy_table("projects", queryset, full_path)


@register(
    "rulebooks_table",
    "1.0",
    format="csv",
    description="Data on rulebooks",
)
def rulebooks_table(
    since: datetime, full_path: str, until: datetime, **kwargs
) -> list[str]:
    queryset = _get_query(models.Rulebook.objects, since, until)

    return _copy_table("rulebooks", queryset, full_path)


@register(
    "rulebook_processes_table",
    "1.0",
    format="csv",
    description="Data on rulebook_processes",
)
def rulebook_processes_table(
    since: datetime, full_path: str, until: datetime, **kwargs
) -> list[str]:
    args = {"started_at": True}
    queryset = _get_query(models.RulebookProcess.objects, since, until, **args)

    return _copy_table("rulebook_processes", queryset, full_path)


@register(
    "organizations_table",
    "1.0",
    format="csv",
    description="Data on organizations",
)
def organizations_table(
    since: datetime, full_path: str, until: datetime, **kwargs
) -> list[str]:
    args = {"created": True}
    queryset = _get_query(
        models.Organization.objects, since, until, **args
    ).values(
        "id",
        "modified",
        "created",
        "name",
        "description",
    )

    return _copy_table("organizations", queryset, full_path)


@register(
    "teams_table",
    "1.0",
    format="csv",
    description="Data on teams",
)
def teams_table(
    since: datetime, full_path: str, until: datetime, **kwargs
) -> list[str]:
    args = {"created": True}
    queryset = _get_query(models.Team.objects, since, until, **args)

    return _copy_table("teams", queryset, full_path)


@register(
    "activation_sources",
    "1.0",
    description="Event Sources used by activations",
)
def activation_sources(
    since: datetime, full_path: str, until: datetime, **kwargs
) -> dict[str, dict[str, Any]]:
    sources = {}
    activations = models.Activation.objects.filter(
        Q(created_at__gt=since, created_at__lte=until)
        | Q(modified_at__gt=since, modified_at__lte=until)
    ).distinct()

    for activation in activations:
        source_data = _gen_source_data(activation)
        stream_data = _gen_stream_data(activation)
        event_stream_ids = [
            stream.id for stream in activation.event_streams.all()
        ]
        for src, occurrence in source_data:
            data = sources.get(src, {})

            data["occurrence"] = data.get("occurrence", 0) + occurrence

            activation_ids_set = set(data.get("activation_ids", []))
            activation_ids_set.add(activation.id)
            data["activation_ids"] = list(activation_ids_set)

            event_stream_ids_set = set(data.get("event_stream_ids", []))
            event_stream_ids_set.update(event_stream_ids)
            if event_stream_ids_set:
                data["event_stream_ids"] = list(event_stream_ids_set)

            event_streams = data.get("event_streams", {})
            for stream, counter in stream_data:
                event_streams[stream] = event_streams.get(stream, 0) + counter

            if event_streams:
                data["event_streams"] = event_streams

            sources[src] = data

    return sources


def _gen_source_data(
    activation: models.Activation,
) -> Generator[Tuple[Any, int], None, None]:
    try:
        rulesets = yaml.safe_load(activation.rulebook_rulesets)
    except yaml.MarkedYAMLError as ex:
        raise ParseError("Failed to parse rulebook data") from ex

    source_types = []
    for ruleset in rulesets:
        for source in ruleset.get("sources", []):
            keys = source.keys()
            types = [item for item in keys if item not in SOURCE_RESERVED_KEYS]
            source_types.extend(types)

    sources_dict = Counter(source_types)

    yield from sources_dict.items()


def _gen_stream_data(
    activation: models.Activation,
) -> Generator[Tuple[Any, int], None, None]:
    stream_types = [
        stream.event_stream_type for stream in activation.event_streams.all()
    ]

    stream_dict = Counter(stream_types)

    yield from stream_dict.items()


def _get_query(
    objects: Manager, since: datetime, to: datetime, **kwargs
) -> str:
    """Construct sql query with datetime params."""
    if kwargs.get("started_at"):
        qs = (
            objects.filter(
                Q(started_at__gt=since, started_at__lte=to)
                | Q(updated_at__gt=since, updated_at__lte=to)
            )
            .order_by("id")
            .distinct()
        )
    elif kwargs.get("created"):
        qs = (
            objects.filter(
                Q(created__gt=since, created__lte=to)
                | Q(modified__gt=since, modified__lte=to)
            )
            .order_by("id")
            .distinct()
        )
    else:
        qs = (
            objects.filter(
                Q(created_at__gt=since, created_at__lte=to)
                | Q(modified_at__gt=since, modified_at__lte=to)
            )
            .order_by("id")
            .distinct()
        )

    return qs


def _get_audit_event_query(actions: list[models.AuditAction]) -> QuerySet:
    events = models.AuditEvent.objects.none()
    for action in actions:
        events |= action.audit_events.all()

    if not bool(events):
        return

    return events.distinct()


def _get_audit_rule_qs(since: datetime, until: datetime) -> QuerySet:
    activation_instance_ids = (
        models.RulebookProcess.objects.filter(
            Q(
                started_at__gt=since.isoformat(),
                started_at__lte=until.isoformat(),
            )
            | Q(
                updated_at__gt=since.isoformat(),
                updated_at__lte=until.isoformat(),
            )
        )
        .values_list("id", flat=True)
        .distinct()
    )

    if len(activation_instance_ids) == 0:
        return models.AuditRule.objects.none()

    if len(activation_instance_ids) == 1:
        audit_rules = models.AuditRule.objects.filter(
            activation_instance_id=activation_instance_ids[0]
        ).order_by("id")
    else:
        audit_rules = models.AuditRule.objects.filter(
            activation_instance_id__in=tuple(activation_instance_ids)
        ).order_by("id")
    return audit_rules


def _get_audit_action_qs(since: datetime, until: datetime) -> QuerySet:
    audit_rules = _get_audit_rule_qs(since, until)
    audit_rule_ids = audit_rules.values_list("id").distinct()

    if len(audit_rule_ids) == 0:
        return models.AuditRule.objects.none()

    if len(audit_rule_ids) == 1:
        audit_actions = models.AuditAction.objects.filter(
            audit_rule_id=audit_rule_ids[0],
        ).order_by("id")
    else:
        audit_actions = models.AuditAction.objects.filter(
            audit_rule_id__in=tuple(audit_rule_ids)
        ).order_by("fired_at")

    return audit_actions


def _copy_table(
    table: str, queryset: QuerySet, path: str, buffer_size: int = 1024 * 1024
) -> Optional[List[str]]:
    """Export large datasets to CSV files using PostgreSQL COPY.

    Args:
        table (str): Source table name for file naming
        query (QuerySet): Django QuerySet generating the COPY command, include:
                          - Filter conditions
                          - Selected fields
                          Example: Model.objects.filter(...).values(...)
        path (str): Output directory path with write permissions
        buffer_size (int): In-memory buffer size in bytes.
                           (Default: 1048576 = 1MB)

    Returns:
        Optional[List[str]]:
        On success: List of chunked file paths
        On failure: None

    Raises:
        DatabaseError: Connection/query failures
        IOError: Filesystem permission issues
    """
    try:
        view_name = f"temp_{table}_{uuid.uuid4().hex[:8]}"
        file_path = os.path.join(path, table + "_table.csv")
        file = CsvFileSplitter(filespec=file_path)

        with connection.cursor() as cursor:
            sql, params = queryset.query.sql_with_params()
            create_view_sql = f"""
                CREATE TEMPORARY VIEW {view_name} AS
                {sql}
            """
            cursor.execute(create_view_sql, params)

            copy_sql = f"""
                COPY (SELECT * FROM {view_name})
                TO STDOUT WITH CSV HEADER
            """
            with cursor.copy(copy_sql) as copy:
                while True:
                    data = copy.read()
                    if not data:
                        break
                    byte_data = bytes(data)
                    # Process data in chunks of buffer_size
                    for i in range(0, len(byte_data), buffer_size):
                        chunk = byte_data[i : i + buffer_size]
                        file.write(chunk.decode())

            cursor.execute(f"DROP VIEW IF EXISTS {view_name}")
        return file.file_list()
    except DatabaseError as e:
        logger.error(f"Database error occurred: {e}")
        return None
    except IOError as e:
        logger.error(f"File I/O error occurred: {e}")
        return None
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
        return None
