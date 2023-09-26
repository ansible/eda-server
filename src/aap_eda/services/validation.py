#  Copyright 2023 Red Hat, Inc.
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
import logging
import urllib.parse

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from aap_eda.core import models
from aap_eda.core.enums import ActivationStatus
from aap_eda.services.ruleset.activate_rulesets import ACTIVATION_PATH

logger = logging.getLogger(__name__)


def validate_activation(activation_id: int) -> bool:
    with transaction.atomic():
        activation = (
            models.Activation.objects.select_for_update()
            .filter(id=activation_id)
            .first()
        )

        try:
            _validate_awx_token(activation.user.id)
            if activation.decision_environment:
                _validate_decision_environment(
                    activation.decision_environment.id
                )

            if activation.rulebook:
                _validate_rulebook(activation.rulebook.id)

            if activation.extra_var:
                _validate_extra_var(activation.extra_var.id)
        except ValidationError as err:
            activation.status = ActivationStatus.ERROR
            activation.status_message = str(err)
            activation.save(update_fields=["status", "status_message"])

            logger.error(err)
            return False

        return True


def validate_activation_creation(
    decision_environment_id: int,
    rulebook_id: int,
    user_id: int,
    extra_var_id: int,
) -> None:
    _validate_awx_token(user_id)
    _validate_decision_environment(decision_environment_id)
    _validate_extra_var(extra_var_id)
    _validate_rulebook(rulebook_id)
    _validate_websocket()


def _validate_awx_token(user_id) -> None:
    tokens = models.AwxToken.objects.filter(user_id=user_id).count()
    if tokens == 0:
        raise ValidationError(_("No controller token specified"))
    elif tokens > 1:
        raise ValidationError(
            _(
                "More than one controller token found, "
                "currently only 1 token is supported"
            )
        )


def _validate_websocket() -> None:
    ws_url = f"{settings.WEBSOCKET_BASE_URL}{ACTIVATION_PATH}"
    parsed_url = urllib.parse.urlparse(ws_url)

    if parsed_url.scheme not in ["ws", "wss"]:
        raise ValidationError(
            _(
                "Connection Error: Invalid WebSocket URL scheme. "
                "Scheme should be either 'ws' or 'wss'."
            )
        )
    if not parsed_url.hostname:
        raise ValidationError(
            _(
                "Connection Error: WebSocket URL must have a valid "
                "host address."
            )
        )


def _validate_decision_environment(decision_environment_id: int) -> None:
    try:
        decision_environment = models.DecisionEnvironment.objects.get(
            id=decision_environment_id
        )
        if decision_environment.credential:
            models.Credential.objects.get(
                id=decision_environment.credential.id
            )
    except models.Credential.DoesNotExist:
        raise ValidationError(_("credential matching query does not exist"))
    except models.DecisionEnvironment.DoesNotExist:
        raise ValidationError(
            _("decision_environment matching query does not exist")
        )


def _validate_rulebook(rulebook_id: int) -> None:
    try:
        models.Rulebook.objects.get(id=rulebook_id)
    except models.Rulebook.DoesNotExist:
        raise ValidationError(_("rulebook matching query does not exist"))


def _validate_extra_var(extra_var_id: int) -> None:
    try:
        models.ExtraVar.objects.get(id=extra_var_id)
    except models.ExtraVar.DoesNotExist:
        raise ValidationError(_("extra_var matching query does not exist"))
