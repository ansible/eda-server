import base64
import json
import logging
import typing as tp
from datetime import datetime
from enum import Enum
from urllib.parse import urlparse, urlunparse

import yaml
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from django.db import DatabaseError
from django.utils import timezone

from aap_eda.api.vault import encrypt_string
from aap_eda.core import models
from aap_eda.core.enums import DefaultCredentialType
from aap_eda.core.exceptions import (
    DuplicateEnvKeyError,
    DuplicateFileTemplateKeyError,
)
from aap_eda.core.models.activation import ActivationStatus
from aap_eda.core.utils.credentials import get_secret_fields
from aap_eda.core.utils.strings import extract_variables, substitute_variables
from aap_eda.tasks import orchestrator

from .messages import (
    ActionMessage,
    AnsibleEventMessage,
    ControllerInfo,
    EndOfResponse,
    EnvVars,
    ExtraVars,
    FileContentMessage,
    HeartbeatMessage,
    JobMessage,
    Rulebook,
    VaultCollection,
    VaultPassword,
    WorkerMessage,
)

logger = logging.getLogger(__name__)

BINARY_FORMATS = {"binary_base64"}


class MessageType(Enum):
    ACTION = "Action"
    ANSIBLE_EVENT = "AnsibleEvent"
    JOB = "Job"
    WORKER = "Worker"
    SHUTDOWN = "Shutdown"
    PROCESSED_EVENT = "ProcessedEvent"
    SESSION_STATS = "SessionStats"
    FILE_CONTENTS = "FileContents"


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
        except DatabaseError as err:
            logger.error(f"Failed to parse {data} due to DB error: {err}")

    async def handle_workers(self, message: WorkerMessage):
        logger.info(f"Start to handle workers: {message}")
        activation = await self.get_activation(message.activation_id)
        rulesets = activation.rulebook_rulesets
        extra_var = activation.extra_var

        rulebook_message = Rulebook(
            data=base64.b64encode(rulesets.encode()).decode()
        )
        if extra_var:
            extra_var_message = ExtraVars(
                data=base64.b64encode(extra_var.encode()).decode()
            )
            await self.send(text_data=extra_var_message.json())

        await self.send(text_data=rulebook_message.json())

        controller_info = await self.get_controller_info(activation)
        if controller_info:
            await self.send(text_data=controller_info.json())

        eda_vault_data = await self.get_eda_system_vault_passwords(activation)
        if eda_vault_data:
            vault_collection = VaultCollection(data=eda_vault_data)
            await self.send(text_data=vault_collection.json())

        file_contents = await self.get_file_contents_from_credentials(
            activation
        )
        for file_content in file_contents:
            await self.send(text_data=file_content.json())

        env_var = await self.get_env_vars_from_credentials(activation)
        if env_var:
            env_var_message = EnvVars(
                data=base64.b64encode(env_var.encode()).decode()
            )
            await self.send(text_data=env_var_message.json())

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

        instance = models.RulebookProcess.objects.filter(
            id=message.activation_id
        ).first()

        if instance:
            instance.updated_at = message.reported_at or timezone.now()
            instance.save(update_fields=["updated_at"])

            activation = instance.get_parent()
            activation.ruleset_stats[
                message.stats["ruleSetName"]
            ] = message.stats
            activation.save(update_fields=["ruleset_stats"])

            if activation.status == ActivationStatus.STARTING:
                orchestrator.enqueue_monitor_rulebook_processes()
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
        job_instance_id = None
        if message.job_id:
            job_instance = models.JobInstance.objects.filter(
                uuid=message.job_id
            ).first()
            job_instance_id = job_instance.id if job_instance else None

        audit_rule = models.AuditRule.objects.filter(
            rule_uuid=message.rule_uuid, fired_at=message.rule_run_at
        ).first()

        activation_instance = models.RulebookProcess.objects.filter(
            id=message.activation_id
        ).first()
        if audit_rule is None:
            activation_org = models.Organization.objects.filter(
                id=activation_instance.organization.id
            ).first()
            audit_rule = models.AuditRule.objects.create(
                activation_instance_id=message.activation_id,
                name=message.rule,
                rule_uuid=message.rule_uuid,
                ruleset_uuid=message.ruleset_uuid,
                ruleset_name=message.ruleset,
                fired_at=message.rule_run_at,
                job_instance_id=job_instance_id,
                status=message.status,
                organization=activation_org,
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
            inputs = {}
            aap_credential_type = models.CredentialType.objects.filter(
                name=DefaultCredentialType.AAP
            )
            if aap_credential_type:
                credentials = (
                    activation_instance.get_parent().eda_credentials.filter(
                        credential_type_id=aap_credential_type[0].id
                    )
                )
                if credentials:
                    inputs = yaml.safe_load(
                        credentials[0].inputs.get_secret_value()
                    )

            url = self._get_url(message, inputs)
            audit_action = models.AuditAction.objects.create(
                id=message.action_uuid,
                fired_at=message.run_at,
                name=message.action,
                url=url,
                status=message.status,
                rule_fired_at=message.rule_run_at,
                audit_rule_id=audit_rule.id,
                status_message=message.message,
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
    def get_activation(self, rulebook_process_id: str) -> models.Activation:
        rulebook_process_instance = models.RulebookProcess.objects.get(
            id=rulebook_process_id
        )
        return rulebook_process_instance.get_parent()

    @database_sync_to_async
    def get_awx_token(self, activation: models.Activation) -> tp.Optional[str]:
        """Get AWX token from the worker message."""
        if not hasattr(activation, "awx_token"):
            return None

        awx_token = activation.awx_token
        return awx_token.token.get_secret_value() if awx_token else None

    async def get_controller_info(
        self, activation: models.Activation
    ) -> tp.Optional[ControllerInfo]:
        """Get Controller Info."""
        controller_info = await self.get_controller_info_from_aap_cred(
            activation
        )
        if controller_info:
            return controller_info

        awx_token = await self.get_awx_token(activation)
        if awx_token:
            return ControllerInfo(
                url=settings.EDA_CONTROLLER_URL,
                token=awx_token,
                ssl_verify=settings.EDA_CONTROLLER_SSL_VERIFY,
            )
        return None

    @database_sync_to_async
    def get_controller_info_from_aap_cred(
        self, activation: models.Activation
    ) -> tp.Optional[ControllerInfo]:
        """Get AAP Credential from Activation."""
        aap_credential_type = models.CredentialType.objects.get(
            name=DefaultCredentialType.AAP
        )
        for eda_credential in activation.eda_credentials.all():
            if eda_credential.credential_type.id == aap_credential_type.id:
                inputs = yaml.safe_load(
                    eda_credential.inputs.get_secret_value()
                )
                return ControllerInfo(
                    url=inputs["host"],
                    token=inputs.get("oauth_token", ""),
                    ssl_verify="yes" if inputs.get("verify_ssl") else "no",
                    username=inputs.get("username", ""),
                    password=inputs.get("password", ""),
                )

        return None

    @database_sync_to_async
    def get_eda_system_vault_passwords(
        self, activation: models.Activation
    ) -> tp.List[VaultPassword]:
        """Get vault info from activation."""
        vault_passwords = []

        if activation.eda_system_vault_credential:
            vault = models.EdaCredential.objects.filter(
                id=activation.eda_system_vault_credential.id
            )
        else:
            vault = models.EdaCredential.objects.none()

        vault_credential_type = models.CredentialType.objects.get(
            name=DefaultCredentialType.VAULT
        )
        for credential in activation.eda_credentials.filter(
            credential_type_id=vault_credential_type.id
        ).union(vault):
            inputs = yaml.safe_load(credential.inputs.get_secret_value())

            vault_passwords.append(
                VaultPassword(
                    label=inputs.get("vault_id", ""),
                    password=inputs["vault_password"],
                )
            )

        return vault_passwords

    def _get_url(self, message: ActionMessage, inputs: dict) -> str:
        if message.action not in ("run_job_template", "run_workflow_template"):
            return ""
        url = message.url

        if not message.controller_job_id:
            return url

        if not inputs:
            return url

        api_url = inputs["host"]
        urlparts = urlparse(api_url)

        path = urlparts.path.rstrip("/")
        if path == "":
            path = "/"
        if path in settings.API_PATH_TO_UI_PATH_MAP:
            path = settings.API_PATH_TO_UI_PATH_MAP[path]

        if message.action == "run_job_template":
            slug = f"{path}/jobs/playbook/{message.controller_job_id}/details/"
        else:
            slug = f"{path}/jobs/workflow/{message.controller_job_id}/details/"

        result = urlunparse(
            [
                urlparts.scheme,
                urlparts.netloc,
                slug,
                urlparts.params,
                urlparts.query,
                urlparts.fragment,
            ]
        )
        logger.debug("Updated Job URL %s", result)
        return result

    @database_sync_to_async
    def get_file_contents_from_credentials(
        self, activation: models.Activation
    ) -> tp.Optional[list[FileContentMessage]]:
        file_template_names = []
        file_messages = []
        for eda_credential in activation.eda_credentials.all():
            inputs = yaml.safe_load(eda_credential.inputs.get_secret_value())
            injectors = eda_credential.credential_type.injectors
            binary_fields = []
            for field in eda_credential.credential_type.inputs.get(
                "fields", []
            ):
                if field.get("format") in BINARY_FORMATS:
                    binary_fields.append(field["id"])

            for template, value in injectors.get("file", {}).items():
                if template in file_template_names:
                    raise DuplicateFileTemplateKeyError(
                        f"{template} already exists"
                    )
                message = self.get_file_content_message(
                    template, binary_fields, value, inputs
                )
                if not message:
                    logger.info(
                        f"{template} is skipped because its content is empty"
                    )
                    continue
                file_template_names.append(template)
                file_messages.append(message)
        return file_messages

    @database_sync_to_async
    def get_env_vars_from_credentials(
        self, activation: models.Activation
    ) -> tp.Optional[str]:
        vault_password, vault_id = self.get_vault_password_and_id(activation)
        env_vars = {}

        for eda_credential in activation.eda_credentials.all():
            schema_inputs = eda_credential.credential_type.inputs
            secret_fields = get_secret_fields(schema_inputs)
            injectors = eda_credential.credential_type.injectors
            user_inputs = yaml.safe_load(
                eda_credential.inputs.get_secret_value()
            )
            if "env" not in injectors:
                continue

            if secret_fields:
                self.encrypt_user_inputs(
                    secret_fields=secret_fields,
                    user_inputs=user_inputs,
                    password=vault_password,
                    vault_id=vault_id,
                )

            for key, value in injectors["env"].items():
                if key in env_vars:
                    raise DuplicateEnvKeyError(f"env {key} already exists")
                env_vars[key] = (
                    value
                    if not isinstance(value, str) or "eda.filename" in value
                    else substitute_variables(value, user_inputs)
                )

        if not env_vars:
            return None
        return yaml.dump(env_vars)

    @staticmethod
    def encrypt_user_inputs(
        secret_fields: list[str],
        user_inputs: dict,
        password: str,
        vault_id: str,
    ) -> None:
        for key, value in user_inputs.items():
            if key in secret_fields:
                user_inputs[key] = encrypt_string(
                    password=password,
                    plaintext=value,
                    vault_id=vault_id,
                )

    @staticmethod
    def get_vault_password_and_id(
        activation: models.Activation,
    ) -> [tp.Optional[str], tp.Optional[str]]:
        if activation.eda_system_vault_credential:
            vault_inputs = activation.eda_system_vault_credential.inputs
            vault_inputs = yaml.safe_load(vault_inputs.get_secret_value())
            return vault_inputs["vault_password"], vault_inputs["vault_id"]
        return None, None

    @staticmethod
    def get_file_content_message(
        template: str, binary_fields: list[str], value: str, inputs: dict
    ) -> tp.Optional[FileContentMessage]:
        binary_file = any(
            attr in binary_fields for attr in extract_variables(value)
        )

        contents = str(substitute_variables(value, inputs))
        if not contents:
            return None
        if binary_file:
            return FileContentMessage(
                template_key=template,
                data=contents,
                data_format="binary",
                eof=True,
            )
        return FileContentMessage(
            template_key=template,
            data=base64.b64encode(contents.encode()).decode(),
            eof=True,
        )
