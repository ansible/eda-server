import base64
import json
import logging
from datetime import datetime
from enum import Enum

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

from aap_eda.core import models

logger = logging.getLogger(__name__)


# Determine host status based on event type
# https://github.com/ansible/awx/blob/devel/awx/main/models/events.py#L164
class Event(Enum):
    FAILED = "runner_on_failed"
    OK = "runner_on_ok"
    ERROR = "runner_on_error"
    SKIPPED = "runner_on_skipped"
    UNREACHABLE = "runner_on_unreachable"
    NO_HOSTS = "runner_on_no_hosts"
    POLLING = "runner_on_async_poll"
    ASYNC_OK = "runner_on_async_ok"
    ASYNC_FAILURE = "runner_on_async_failed"
    RETRY = "runner_retry"
    NO_MATCHED = "playbook_on_no_hosts_matched"
    NO_REMAINING = "playbook_on_no_hosts_remaining"


host_status_map = {
    Event.FAILED: "failed",
    Event.OK: "ok",
    Event.ERROR: "failed",
    Event.SKIPPED: "skipped",
    Event.UNREACHABLE: "unreachable",
    Event.NO_HOSTS: "no remaining",
    Event.POLLING: "polling",
    Event.ASYNC_OK: "async ok",
    Event.ASYNC_FAILURE: "async failure",
    Event.RETRY: "retry",
    Event.NO_MATCHED: "no matched",
    Event.NO_REMAINING: "no remaining",
}

route_prefix = f"{settings.API_PREFIX}/api/ws2/"


class EchoConsumer(AsyncWebsocketConsumer):
    async def receive(self, text_data=None, bytes_data=None):
        await self.send(text_data)


class AnsibleRulebookConsumer(AsyncWebsocketConsumer):
    async def receive(self, text_data=None, bytes_data=None):
        self.send(text_data=json.dumps({"type": "Hello"}))

        data = json.loads(text_data)
        logger.debug(f"AnsibleRulebookConsumer received: {data}")

        data_type = data.get("type")

        if data_type == "Worker":
            await self.handle_workers(data)
        elif data_type == "Job":
            await self.handle_jobs(data)
        elif data_type == "AnsibleEvent":
            await self.handle_events(data)
        elif data_type == "Action":
            await self.handle_actions(data)
        else:
            logger.warning(f"Unsupported data type received: {data_type}")

    async def handle_workers(self, data: dict):
        rulebook, inventory, extra_var = await self.get_resources(
            data.get("activation_id")
        )

        await self.send(
            text_data=json.dumps(
                {
                    "type": "Rulebook",
                    "data": base64.b64encode(
                        rulebook.rulesets.encode()
                    ).decode(),
                }
            )
        )

        await self.send(
            text_data=json.dumps(
                {
                    "type": "Inventory",
                    "data": base64.b64encode(
                        inventory.inventory.encode()
                    ).decode(),
                }
            )
        )

        await self.send(
            text_data=json.dumps(
                {
                    "type": "ExtraVars",
                    "data": base64.b64encode(
                        extra_var.extra_var.encode()
                    ).decode(),
                }
            )
        )

        # TODO: create SSHPrivateKey later
        await self.send(
            text_data=json.dumps({"type": "SSHPrivateKey", "data": ""})
        )

        # TODO: add update manager broadcast later

    async def handle_jobs(self, data: dict):
        logger.info(f"Start to handle jobs: {data}")
        await self.insert_job_related_data(data)

    async def handle_events(self, data: dict):
        logger.info(f"Start to handle events: {data}")
        await self.insert_event_related_data(data)

    async def handle_actions(self, data: dict):
        logger.info(f"Start to handle actions: {data}")
        await self.insert_audit_rule_data(data)

    @database_sync_to_async
    def insert_event_related_data(self, data: dict) -> None:
        event_data = data.get("event", {})
        if event_data.get("stdout"):
            job_instance = models.JobInstance.objects.get(
                uuid=event_data.get("job_id")
            )

            # TODO: broadcasting
            logger.debug(f"Job instance {job_instance.id} is broadcasting.")

        created = event_data.get("created")
        if created:
            created = datetime.strptime(created, "%Y-%m-%dT%H:%M:%S.%f")

        job_instance_event = models.JobInstanceEvent.objects.create(
            job_uuid=event_data.get("job_id"),
            counter=event_data.get("counter"),
            stdout=event_data.get("stdout"),
            type=event_data.get("event"),
            created_at=created,
        )
        logger.info(f"Job instance event {job_instance_event.id} is created.")

        event = event_data.get("event")
        if event and event in [item.value for item in host_status_map]:
            data = event_data.get("event_data", {})

            playbook = data.get("playbook")
            play = data.get("play")
            task = data.get("task")
            status = host_status_map[Event(event)]

            if event == "runner_on_ok" and data.get("res", {}).get("changed"):
                status = "changed"

            job_instance_host = models.JobInstanceHost.objects.create(
                job_uuid=event_data.get("job_id"),
                playbook=playbook,
                play=play,
                task=task,
                status=status,
            )
            logger.info(
                f"Job instance host {job_instance_host.id} is created."
            )

    @database_sync_to_async
    def insert_audit_rule_data(self, data: dict) -> None:
        activation_instance_id = int(data.get("activation_id"))

        if activation_instance_id:
            action_name = data.get("action")
            playbook_name = data.get("playbook_name")
            job_id = data.get("job_id")
            fired_date = datetime.strptime(
                data.get("run_at"), "%Y-%m-%d %H:%M:%S.%f"
            )
            status = data.get("status")

            if job_id:
                job_instance = models.JobInstance.objects.get(uuid=job_id)

            activation_instance = models.ActivationInstance.objects.get(
                id=activation_instance_id
            )
            activation = models.Activation.objects.get(
                id=activation_instance.activation_id
            )
            rulesets = models.Ruleset.objects.filter(
                rulebook_id=activation.rulebook_id
            )

            rules = models.Rule.objects.filter(
                ruleset_id__in=[ruleset.id for ruleset in rulesets]
            )

            audit_rules = []
            if job_instance:
                for rule in rules:
                    if (
                        rule.action.get(action_name, {}).get("name")
                        == playbook_name
                    ):
                        audit_rule = models.AuditRule(
                            activation_instance_id=activation_instance_id,
                            ruleset_id=rule.ruleset_id,
                            rule_id=rule.id,
                            name=rule.name,
                            definition=rule.action,
                            job_instance_id=job_instance.id,
                            fired_date=fired_date,
                            status=status,
                        )
                        audit_rules.append(audit_rule)
            else:
                for rule in rules:
                    if (
                        rule.action.get(action_name, {}).get("name")
                        == playbook_name
                    ):
                        audit_rule = models.AuditRule(
                            activation_instance_id=activation_instance_id,
                            ruleset_id=rule.ruleset_id,
                            rule_id=rule.id,
                            name=rule.name,
                            definition=rule.action,
                            fired_date=fired_date,
                            status=status,
                        )
                        audit_rules.append(audit_rule)

            if len(audit_rules) > 0:
                models.AuditRule.objects.bulk_create(audit_rules)
                logger.info(f"{len(audit_rules)} audit rules are created.")

    @database_sync_to_async
    def insert_job_related_data(self, data: dict) -> models.JobInstance:
        job_instance = models.JobInstance.objects.create(
            uuid=data.get("job_id"),
            name=data.get("name"),
            action=data.get("action"),
            ruleset=data.get("ruleset"),
            hosts=data.get("hosts"),
            rule=data.get("rule"),
        )
        logger.info(f"Job instance {job_instance.id} is created.")

        activation_instance_id = int(data.get("ansible_rulebook_id"))
        instance = models.ActivationInstanceJobInstance.objects.create(
            job_instance_id=job_instance.id,
            activation_instance_id=activation_instance_id,
        )
        logger.info(f"ActivationInstanceJobInstance {instance.id} is created.")

        return job_instance

    @database_sync_to_async
    def get_resources(self, activation_id: str):
        activation_instance = models.ActivationInstance.objects.get(
            id=activation_id
        )
        activation = models.Activation.objects.get(
            id=activation_instance.activation_id
        )
        rulebook = models.Rulebook.objects.get(id=activation.rulebook_id)
        inventory = models.Inventory.objects.get(
            project_id=activation.project_id
        )
        extra_var = models.ExtraVar.objects.get(id=activation.extra_var_id)
        return (rulebook, inventory, extra_var)
