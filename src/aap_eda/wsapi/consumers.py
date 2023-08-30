import base64
import json
import logging
from datetime import datetime
from enum import Enum

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from django.db import IntegrityError

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus
from aap_eda.core.exceptions import AwxTokenNotFound
from aap_eda.core.utils.awx_token import get_awx_token
from aap_eda.services.ruleset.activate_rulesets import ActivationDbLogger

from .messages import (
    ActionMessage,
    AnsibleEventMessage,
    ControllerInfo,
    EndOfResponse,
    ExtraVars,
    HeartbeatMessage,
    JobMessage,
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
    SESSION_STATS = "SessionStats"


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

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"


class AnsibleRulebookConsumer(AsyncWebsocketConsumer):
    async def receive(self, text_data=None, bytes_data=None):
        await self.send(text_data=json.dumps({"type": "Hello"}))

        data = json.loads(text_data)
        logger.debug(f"AnsibleRulebookConsumer received: {data}")

        msg_type = MessageType(data.get("type"))

        try:
            if msg_type == MessageType.WORKER:
                await self.handle_workers(WorkerMessage.parse_obj(data))
            elif msg_type == MessageType.JOB:
                await self.handle_jobs(JobMessage.parse_obj(data))
            # AnsibleEvent messages are no longer sent by ansible-rulebook
            # TODO: remove later if no need to keep
            elif msg_type == MessageType.ANSIBLE_EVENT:
                await self.handle_events(AnsibleEventMessage.parse_obj(data))
            elif msg_type == MessageType.ACTION:
                await self.handle_actions(ActionMessage.parse_obj(data))
            elif msg_type == MessageType.SHUTDOWN:
                logger.info("Websocket connection is closed.")
            elif msg_type == MessageType.SESSION_STATS:
                await self.handle_heartbeat(HeartbeatMessage.parse_obj(data))
            else:
                logger.warning(f"Unsupported message received: {data}")
        except IntegrityError as e:
            logger.error(f"{str(e)}")

    async def handle_workers(self, message: WorkerMessage):
        # AWX token must be present before continue
        user_id = await get_user_id_from_instance_id(message.activation_id)
        try:
            awx_token = await sync_to_async(get_awx_token)(user_id=user_id)
        except AwxTokenNotFound:
            logger.error("Worker can not continue, AwxToken not found.")
            fail_msg = (
                "ERROR: Activation instance failed: AWX token not found."
            )

            # TODO(aizquierdo): This should not be placed in the
            # activation_logger, but in the activation_instance
            # https://issues.redhat.com/browse/AAP-15495
            await write_instance_log(message.activation_id, fail_msg)
            raise

        logger.info(f"Start to handle workers: {message}")
        rulesets, extra_var = await self.get_resources(message.activation_id)

        rulebook_message = Rulebook(
            data=base64.b64encode(rulesets.encode()).decode()
        )
        if extra_var:
            extra_var_message = ExtraVars(
                data=base64.b64encode(extra_var.extra_var.encode()).decode()
            )
            await self.send(text_data=extra_var_message.json())

        controller_info = ControllerInfo(
            url=settings.EDA_CONTROLLER_URL,
            token=awx_token,
            ssl_verify=settings.EDA_CONTROLLER_SSL_VERIFY,
        )

        await self.send(text_data=rulebook_message.json())
        await self.send(text_data=controller_info.json())
        await self.send(text_data=EndOfResponse().json())

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
    def handle_heartbeat(self, message: HeartbeatMessage) -> None:
        logger.info(f"Start to handle heartbeat: {message}")

        instance = models.ActivationInstance.objects.filter(
            id=message.activation_id
        ).first()

        if instance:
            instance.status = ActivationStatus.RUNNING
            instance.updated_at = message.reported_at
            instance.save(update_fields=["status", "updated_at"])

            instance.activation.ruleset_stats[
                message.stats["ruleSetName"]
            ] = message.stats
            instance.activation.save(update_fields=["ruleset_stats"])
        else:
            logger.warning(
                f"Activation instance {message.activation_id} is not present."
            )

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
        job_id = message.job_id
        job_instance = models.JobInstance.objects.filter(uuid=job_id).first()
        job_instance_id = job_instance.id if job_instance else None

        audit_rule = models.AuditRule.objects.filter(
            rule_uuid=message.rule_uuid, fired_at=message.rule_run_at
        ).first()
        if audit_rule is None:
            audit_rule = models.AuditRule.objects.create(
                activation_instance_id=message.activation_id,
                name=message.rule,
                rule_uuid=message.rule_uuid,
                ruleset_uuid=message.ruleset_uuid,
                ruleset_name=message.ruleset,
                fired_at=message.rule_run_at,
                job_instance_id=job_instance_id,
                status=message.status,
            )

            logger.info(f"Audit rule [{audit_rule.name}] is created.")
        else:
            # if rule has multiple actions and one of its action's status is
            # 'failed', keep rule's status as 'failed'
            if (
                audit_rule.status != message.status
                and audit_rule.status != "failed"
            ):
                audit_rule.status = message.status
                audit_rule.save()

        audit_action = models.AuditAction.objects.filter(
            id=message.action_uuid
        ).first()

        if audit_action is None:
            audit_action = models.AuditAction.objects.create(
                id=message.action_uuid,
                fired_at=message.run_at,
                name=message.action,
                url=message.url,
                status=message.status,
                rule_fired_at=message.rule_run_at,
                audit_rule_id=audit_rule.id,
            )

            logger.info(f"Audit action [{audit_action.name}] is created.")

        matching_events = message.matching_events
        for event_meta in matching_events.values():
            meta = event_meta.pop("meta")
            if meta:
                audit_event = models.AuditEvent.objects.filter(
                    id=meta.get("uuid")
                ).first()

                if audit_event is None:
                    audit_event = models.AuditEvent.objects.create(
                        id=meta.get("uuid"),
                        source_name=meta.get("source", {}).get("name"),
                        source_type=meta.get("source", {}).get("type"),
                        payload=event_meta,
                        received_at=meta.get("received_at"),
                        rule_fired_at=message.rule_run_at,
                    )
                    logger.info(f"Audit event [{audit_event.id}] is created.")

                audit_event.audit_actions.add(audit_action)
                audit_event.save()

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
    ) -> tuple[str, models.ExtraVar]:
        activation_instance = models.ActivationInstance.objects.get(
            id=activation_instance_id
        )
        activation = models.Activation.objects.get(
            id=activation_instance.activation_id
        )

        if activation.extra_var_id:
            extra_var = models.ExtraVar.objects.filter(
                id=activation.extra_var_id
            ).first()
        else:
            extra_var = None

        return activation.rulebook_rulesets, extra_var


@database_sync_to_async
def get_user_id_from_instance_id(
    activation_instance_id: int,
) -> models.ActivationInstance:
    """
    Retrieve the user ID associated with the given activation instance ID.

    Args:
        activation_instance_id (int): The ID of the activation instance.

    Returns:
        int: The user ID associated with the activation instance.

    Raises:
        models.ActivationInstance.DoesNotExist: If the activation
        instance with the given ID does not exist.

    """
    activation_instance = models.ActivationInstance.objects.get(
        id=activation_instance_id
    )
    return activation_instance.activation.user_id


@database_sync_to_async
def write_instance_log(instance_id: int, msg: str) -> None:
    """
    Asynchronously write a log message for a specific activation instance.

    Args:
        instance_id (int): The ID of the activation instance.
        msg (str): The log message to be written.

    Returns:
        None: This function does not return a value.

    Raises:
        None: This function does not raise any exceptions directly.

    """
    instance = models.ActivationInstance.objects.filter(id=instance_id).first()
    if not instance:
        logger.warning(f"Activation instance {instance_id} is not present.")
        return
    activation_logger = ActivationDbLogger(instance_id)
    activation_logger.write(msg, flush=True)
