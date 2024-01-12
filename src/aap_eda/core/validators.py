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
import typing as tp

import yaml
from rest_framework import serializers

from aap_eda.core import models

logger = logging.getLogger(__name__)


def check_if_rulebook_exists(rulebook_id: int) -> int:
    try:
        models.Rulebook.objects.get(pk=rulebook_id)
    except models.Rulebook.DoesNotExist:
        raise serializers.ValidationError(
            f"Rulebook with id {rulebook_id} does not exist"
        )
    return rulebook_id


def check_if_de_exists(decision_environment_id: int) -> int:
    try:
        de = models.DecisionEnvironment.objects.get(pk=decision_environment_id)
        if de.credential_id:
            models.Credential.objects.get(pk=de.credential_id)
    except models.Credential.DoesNotExist:
        raise serializers.ValidationError(
            f"Credential with id {de.credential_id} does not exist"
        )
    except models.DecisionEnvironment.DoesNotExist:
        raise serializers.ValidationError(
            f"DecisionEnvironment with id {decision_environment_id} "
            "does not exist"
        )
    return decision_environment_id


def check_if_extra_var_exists(extra_var_id: int) -> int:
    try:
        models.ExtraVar.objects.get(pk=extra_var_id)
    except models.ExtraVar.DoesNotExist:
        raise serializers.ValidationError(
            f"ExtraVar with id {extra_var_id} does not exist"
        )
    return extra_var_id


def check_if_awx_token_exists(awx_token_id: int) -> int:
    try:
        models.AwxToken.objects.get(pk=awx_token_id)
    except models.AwxToken.DoesNotExist:
        raise serializers.ValidationError(
            f"AwxToken with id {awx_token_id} does not exist"
        )
    return awx_token_id


def check_rulesets_require_token(
    rulesets_data: list[dict[str, tp.Any]],
) -> bool:
    """Inspect rulesets data to determine if a token is required.

    Return True if any of the rules has an action that requires a token.
    """
    required_actions = {"run_job_template", "run_workflow_template"}

    for ruleset in rulesets_data:
        for rule in ruleset.get("rules", []):
            # When it is a single action dict
            if any(
                action_key in required_actions
                for action_key in rule.get("action", {})
            ):
                return True

            # When it is a list of actions
            if any(
                action_arg in required_actions
                for action in rule.get("actions", [])
                for action_arg in action
            ):
                return True

    return False


def is_extra_var_dict(extra_var: str):
    try:
        data = yaml.safe_load(extra_var)
        if not isinstance(data, dict):
            raise serializers.ValidationError(
                "Extra var is not in object format"
            )
    except yaml.YAMLError:
        raise serializers.ValidationError(
            "Extra var must be in JSON or YAML format"
        )
