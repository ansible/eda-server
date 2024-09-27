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

import os
import platform
from datetime import datetime

import distro
from ansible_base.resource_registry.models.service_identifier import service_id
from django.conf import settings
from django.db import connection
from django.db.models import Manager, Q
from insights_analytics_collector import CsvFileSplitter, register

from aap_eda.analytics.utils import (
    collect_controllers_info,
    extract_job_details,
)
from aap_eda.core import models
from aap_eda.utils import get_eda_version


@register(
    "config",
    "1.0",
    description="General platform configuration.",
    config=True,
)
def config(**kwargs) -> dict:
    install_type = "traditional"
    if os.environ.get("container") == "oci":
        install_type = "openshift"
    elif "KUBERNETES_SERVICE_PORT" in os.environ:
        install_type = "k8s"
    return {
        "install_uuid": service_id(),
        "platform": {
            "system": platform.system(),
            "dist": distro.linux_distribution(),
            "release": platform.release(),
            "type": install_type,
        },
        # skip license related info so far
        "eda_log_level": settings.APP_LOG_LEVEL,
        "eda_version": get_eda_version(),
        "eda_deployment_type": settings.DEPLOYMENT_TYPE,
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
    "activations_table",
    "1.0",
    format="csv",
    description="Data on activations",
)
def activations_table(
    since: datetime, full_path: str, until: datetime, **kwargs
):
    query = _get_query(models.Activation.objects, since, until)

    return _copy_table("activations", query, full_path)


@register(
    "audit_action_table",
    "1.0",
    format="csv",
    description="Data on audit_actions",
)
def audit_actions_table(
    since: datetime, full_path: str, until: datetime, **kwargs
):
    audit_actions = _get_audit_action_qs(since, until)

    if not bool(audit_actions):
        return

    audit_action_query = (
        f"COPY ({audit_actions.query}) TO STDOUT WITH CSV HEADER"
    )

    return _copy_table("audit_actions", audit_action_query, full_path)


@register(
    "audit_event_table",
    "1.0",
    format="csv",
    description="Data on audit_events",
)
def audit_events_table(
    since: datetime, full_path: str, until: datetime, **kwargs
):
    audit_actions = _get_audit_action_qs(since, until)
    if not bool(audit_actions):
        return

    audit_event_query = _get_audit_event_query(audit_actions)
    if not bool(audit_event_query):
        return

    return _copy_table("audit_events", audit_event_query, full_path)


@register(
    "audit_rule_table",
    "1.0",
    format="csv",
    description="Data on audit_rules",
)
def audit_rules_table(
    since: datetime, full_path: str, until: datetime, **kwargs
):
    audit_rules = _get_audit_rule_qs(since, until)
    if not bool(audit_rules):
        return

    audit_rule_query = f"COPY ({audit_rules.query}) TO STDOUT WITH CSV HEADER"

    return _copy_table("audit_rules", audit_rule_query, full_path)


@register(
    "eda_credential_table",
    "1.0",
    format="csv",
    description="Data on eda_credentials",
)
def eda_credentials_table(
    since: datetime, full_path: str, until: datetime, **kwargs
):
    query = _get_query(models.EdaCredential.objects, since, until)

    return _copy_table("eda_credentials", query, full_path)


@register(
    "credential_type_table",
    "1.0",
    format="csv",
    description="Data on credential_types",
)
def credential_types_table(
    since: datetime, full_path: str, until: datetime, **kwargs
):
    query = _get_query(models.CredentialType.objects, since, until)

    return _copy_table("credential_types", query, full_path)


@register(
    "decision_environment_table",
    "1.0",
    format="csv",
    description="Data on decision_environments",
)
def decision_environments_table(
    since: datetime, full_path: str, until: datetime, **kwargs
):
    query = _get_query(models.DecisionEnvironment.objects, since, until)
    return _copy_table("decision_environments", query, full_path)


@register(
    "event_stream_table",
    "1.0",
    format="csv",
    description="Data on event_streams",
)
def event_streams_table(
    since: datetime, full_path: str, until: datetime, **kwargs
):
    query = _get_query(models.EventStream.objects, since, until)
    return _copy_table("event_streams", query, full_path)


@register(
    "event_streams_by_activation_table",
    "1.0",
    format="csv",
    description="Data on event_streams used by each activation",
)
def event_streams_by_activation_table(
    since: datetime, full_path: str, until: datetime, **kwargs
):
    activations = models.Activation.objects.filter(
        Q(created_at__gt=since, created_at__lte=until)
        | Q(modified_at__gt=since, modified_at__lte=until)
    ).distinct()

    event_streams = models.EventStream.objects.none()
    for activation in activations:
        event_streams |= activation.event_streams.all()

    if not bool(event_streams):
        return

    event_streams = event_streams.extra(
        select={
            "activation_id": "core_activation_event_streams.activation_id",
            "event_stream_id": "core_eventstream.id",
        }
    ).values(
        "activation_id",
        "event_stream_id",
        "name",
        "event_stream_type",
        "eda_credential_id",
        "owner",
        "events_received",
        "last_event_received_at",
        "organization_id",
    )

    query = f"COPY ({event_streams.query}) TO STDOUT WITH CSV HEADER"

    return _copy_table("event_streams_by_activation", query, full_path)


@register(
    "project_table",
    "1.0",
    format="csv",
    description="Data on projects",
)
def projects_table(since: datetime, full_path: str, until: datetime, **kwargs):
    query = _get_query(models.Project.objects, since, until)
    return _copy_table("projects", query, full_path)


@register(
    "rulebook_table",
    "1.0",
    format="csv",
    description="Data on rulebooks",
)
def rulebooks_table(
    since: datetime, full_path: str, until: datetime, **kwargs
):
    query = _get_query(models.Rulebook.objects, since, until)
    return _copy_table("rulebooks", query, full_path)


@register(
    "rulebook_process_table",
    "1.0",
    format="csv",
    description="Data on rulebook_processes",
)
def rulebook_processes_table(
    since: datetime, full_path: str, until: datetime, **kwargs
):
    args = {"started_at": True}
    query = _get_query(models.RulebookProcess.objects, since, until, **args)
    return _copy_table("rulebook_processes", query, full_path)


@register(
    "organization_table",
    "1.0",
    format="csv",
    description="Data on organizations",
)
def organizations_table(
    since: datetime, full_path: str, until: datetime, **kwargs
):
    args = {"created": True}
    query = _get_query(models.Organization.objects, since, until, **args)
    return _copy_table("organizations", query, full_path)


@register(
    "team_table",
    "1.0",
    format="csv",
    description="Data on teams",
)
def teams_table(since: datetime, full_path: str, until: datetime, **kwargs):
    args = {"created": True}
    query = _get_query(models.Team.objects, since, until, **args)

    return _copy_table("teams", query, full_path)


def _datetime_format(dt: datetime) -> str:
    """Convert datetime object to string."""
    if dt.microsecond == 0:
        iso_format = dt.strftime("%Y-%m-%d %H:%M:%S%z")
    else:
        iso_format = dt.strftime("%Y-%m-%d %H:%M:%S.%f%z")

    return iso_format[:-2] + ":" + iso_format[-2:]


def _get_query(
    objects: Manager, since: datetime, until: datetime, **kwargs
) -> str:
    """Construct sql query with datetime params."""
    if kwargs.get("started_at"):
        qs = (
            objects.filter(
                Q(started_at__gt=since, started_at__lte=until)
                | Q(updated_at__gt=since, updated_at__lte=until)
            )
            .order_by("id")
            .distinct()
        )
    elif kwargs.get("created"):
        qs = (
            objects.filter(
                Q(created__gt=since, created__lte=until)
                | Q(modified__gt=since, modified__lte=until)
            )
            .order_by("id")
            .distinct()
        )
    else:
        qs = (
            objects.filter(
                Q(created_at__gt=since, created_at__lte=until)
                | Q(modified_at__gt=since, modified_at__lte=until)
            )
            .order_by("id")
            .distinct()
        )

    query = (
        str(qs.query)
        .replace(_datetime_format(since), f"'{since.isoformat()}'")
        .replace(_datetime_format(until), f"'{until.isoformat()}'")
    )

    return f"COPY ({query}) TO STDOUT WITH CSV HEADER"


def _get_audit_event_query(actions: list[models.AuditAction]):
    events = models.AuditEvent.objects.none()
    for action in actions:
        events |= action.audit_events.all()

    if not bool(events):
        return

    query = str(events.distinct().query)

    for action in actions:
        query = query.replace(str(action.id), f"'{action.id}'")

    return f"COPY ({query}) TO STDOUT WITH CSV HEADER"


def _get_audit_rule_qs(since: datetime, until: datetime):
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
        return models.RulebookProcess.objects.none()

    if len(activation_instance_ids) == 1:
        audit_rules = models.AuditRule.objects.filter(
            activation_instance_id=activation_instance_ids[0]
        ).order_by("id")
    else:
        audit_rules = models.AuditRule.objects.filter(
            activation_instance_id__in=tuple(activation_instance_ids)
        ).order_by("id")

    return audit_rules


def _get_audit_action_qs(since: datetime, until: datetime):
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


def _copy_table(table, query, path):
    file_path = os.path.join(path, table + "_table.csv")
    file = CsvFileSplitter(filespec=file_path)
    with connection.cursor() as cursor:
        with cursor.copy(query) as copy:
            while data := copy.read():
                byte_data = bytes(data)
                file.write(byte_data.decode())
    return file.file_list()
