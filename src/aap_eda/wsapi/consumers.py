import base64
import json
import logging
from datetime import datetime, timezone
from enum import Enum

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from aap_eda.core import models

from .messages import (
    ActionMessage,
    AnsibleEventMessage,
    ExtraVars,
    JobMessage,
    Message,
    Project,
    Rulebook,
    WorkerMessage,
)

logger = logging.getLogger(__name__)


class MessageType(Enum):
    ACTION = "Action"
    ANSIBLE_EVENT = "AnsibleEvent"
    JOB = "Job"
    WORKER = "Worker"
    SHUTDOWN = "Shutdown"
    PROCESSED_EVENT = "ProcessedEvent"


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

BLOCK_SIZE = 4 * 1024


class AnsibleRulebookConsumer(AsyncWebsocketConsumer):
    async def receive(self, text_data=None, bytes_data=None):
        await self.send(text_data=json.dumps({"type": "Hello"}))

        data = json.loads(text_data)
        logger.debug(f"AnsibleRulebookConsumer received: {data}")

        msg_type = MessageType(data.get("type"))

        if msg_type == MessageType.WORKER:
            await self.handle_workers(WorkerMessage.parse_obj(data))
        elif msg_type == MessageType.JOB:
            await self.handle_jobs(JobMessage.parse_obj(data))
        elif msg_type == MessageType.ANSIBLE_EVENT:
            await self.handle_events(AnsibleEventMessage.parse_obj(data))
        elif msg_type == MessageType.ACTION:
            await self.handle_actions(ActionMessage.parse_obj(data))
        elif msg_type == MessageType.SHUTDOWN:
            logger.info("Websocket connection is closed.")
        else:
            logger.warning(f"Unsupported message received: {data}")

    async def handle_workers(self, message: WorkerMessage):
        logger.info(f"Start to handle workers: {message}")
        rulebook, extra_var, project = await self.get_resources(
            message.activation_id
        )

        rulebook_message = Rulebook(
            data=base64.b64encode(rulebook.rulesets.encode()).decode()
        )
        extra_var_message = ExtraVars(
            data=base64.b64encode(extra_var.extra_var.encode()).decode()
        )

        if project.archive_file:
            with open(project.archive_file.path, "rb") as f:
                while filedata := f.read(BLOCK_SIZE):
                    project_data_message = Project(
                        more=True,
                        data=base64.b64encode(filedata).decode("utf-8"),
                    )
                    await self.send(text_data=project_data_message.json())
        else:
            project_data_message = Project()
            await self.send(text_data=project_data_message.json())

        await self.send(text_data=rulebook_message.json())
        await self.send(text_data=extra_var_message.json())
        await self.send(text_data=Message().json())

        # TODO: add broadcasting later by channel groups

    async def handle_jobs(self, message: JobMessage):
        logger.info(f"Start to handle jobs: {message}")
        await self.insert_job_related_data(message)

    async def handle_events(self, message: AnsibleEventMessage):
        logger.info(f"Start to handle events: {message}")
        await self.insert_event_related_data(message)

    async def handle_actions(self, message: ActionMessage):
        logger.info(f"Start to handle actions: {message}")
        await self.insert_audit_rule_data(message)

    @database_sync_to_async
    def insert_event_related_data(self, message: AnsibleEventMessage) -> None:
        event_data = message.event or {}
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
    def insert_audit_rule_data(self, message: ActionMessage) -> None:
        activation_instance_id = message.activation_id

        if activation_instance_id:
            action_name = message.action
            playbook_name = message.playbook_name
            job_id = message.job_id
            fired_date = datetime.strptime(
                message.run_at, "%Y-%m-%d %H:%M:%S.%f"
            ).replace(tzinfo=timezone.utc)
            status = message.status

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
            logger.info(
                f"Found {rules.count()} possible rules for message: {message}"
            )

            audit_rules = []
            job_instance_id = job_instance.id if job_instance else None

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
                        job_instance_id=job_instance_id,
                        fired_date=fired_date,
                        status=status,
                    )
                    audit_rules.append(audit_rule)

            if len(audit_rules) > 0:
                models.AuditRule.objects.bulk_create(audit_rules)
                logger.info(f"{len(audit_rules)} audit rules are created.")

    @database_sync_to_async
    def insert_job_related_data(
        self, message: JobMessage
    ) -> models.JobInstance:
        job_instance = models.JobInstance.objects.create(
            uuid=message.job_id,
            name=message.name,
            action=message.action,
            ruleset=message.ruleset,
            hosts=message.hosts,
            rule=message.rule,
        )
        logger.info(f"Job instance {job_instance.id} is created.")

        activation_instance_id = message.ansible_rulebook_id
        instance = models.ActivationInstanceJobInstance.objects.create(
            job_instance_id=job_instance.id,
            activation_instance_id=activation_instance_id,
        )
        logger.info(f"ActivationInstanceJobInstance {instance.id} is created.")

        return job_instance

    @database_sync_to_async
    def get_resources(
        self, activation_instance_id: str
    ) -> tuple[models.Rulebook, models.inventory, models.ExtraVar]:
        activation_instance = models.ActivationInstance.objects.get(
            id=activation_instance_id
        )
        activation = models.Activation.objects.get(
            id=activation_instance.activation_id
        )
        rulebook = models.Rulebook.objects.get(id=activation.rulebook_id)
        extra_var = models.ExtraVar.objects.get(id=activation.extra_var_id)
        project = models.Project.objects.get(id=activation.project_id)
        return (rulebook, extra_var, project)
