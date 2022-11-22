from collections import namedtuple


AlembicVersion = namedtuple(
    "AlembicVersion",
    [
        "version_num",
    ],
)

ActivationInstanceJobInstance = namedtuple(
    "ActivationInstanceJobInstance",
    [
        "id",
        "activation_instance_id",
        "job_instance_id",
    ],
)

ActivationInstance = namedtuple(
    "ActivationInstance",
    [
        "id",
        "name",
        "rulebook_id",
        "inventory_id",
        "extra_var_id",
        "execution_environment",
        "working_directory",
        "large_data_id",
        "project_id",
    ],
)

ExtraVar = namedtuple(
    "ExtraVar",
    [
        "id",
        "name",
        "extra_var",
        "project_id",
    ],
)

Project = namedtuple(
    "Project",
    [
        "id",
        "git_hash",
        "url",
        "name",
        "description",
        "created_at",
        "modified_at",
        "large_data_id",
    ],
)

Inventory = namedtuple(
    "Inventory",
    [
        "id",
        "name",
        "inventory",
        "project_id",
    ],
)

Rulebook = namedtuple(
    "Rulebook",
    [
        "id",
        "name",
        "rulesets",
        "project_id",
        "description",
        "created_at",
        "modified_at",
    ],
)

JobInstance = namedtuple(
    "JobInstance",
    [
        "id",
        "uuid",
    ],
)

ActivationInstanceLog = namedtuple(
    "ActivationInstanceLog",
    [
        "id",
        "activation_instance_id",
        "line_number",
        "log",
    ],
)

Rule = namedtuple(
    "Rule",
    [
        "id",
        "ruleset_id",
        "name",
        "action",
    ],
)

Ruleset = namedtuple(
    "Ruleset",
    [
        "id",
        "rulebook_id",
        "name",
        "created_at",
        "modified_at",
    ],
)

Job = namedtuple(
    "Job",
    [
        "id",
        "uuid",
    ],
)

Playbook = namedtuple(
    "Playbook",
    [
        "id",
        "name",
        "playbook",
        "project_id",
    ],
)

AuditRule = namedtuple(
    "AuditRule",
    [
        "id",
        "name",
        "description",
        "status",
        "fired_date",
        "created_at",
        "definition",
        "rule_id",
        "ruleset_id",
        "activation_instance_id",
        "job_instance_id",
    ],
)

JobInstanceEvent = namedtuple(
    "JobInstanceEvent",
    [
        "id",
        "job_uuid",
        "counter",
        "stdout",
        "type",
        "created_at",
    ],
)

JobInstanceHost = namedtuple(
    "JobInstanceHost",
    [
        "id",
        "host",
        "job_uuid",
        "playbook",
        "play",
        "task",
        "status",
    ],
)

Activation = namedtuple(
    "Activation",
    [
        "id",
        "name",
        "rulebook_id",
        "inventory_id",
        "extra_var_id",
        "description",
        "status",
        "is_enabled",
        "restarted_at",
        "restart_count",
        "created_at",
        "modified_at",
        "working_directory",
        "execution_environment",
        "restart_policy",
    ],
)

Role = namedtuple(
    "Role",
    [
        "id",
        "name",
        "description",
    ],
)

RolePermission = namedtuple(
    "RolePermission",
    [
        "id",
        "role_id",
        "resource_type",
        "action",
    ],
)

UserRole = namedtuple(
    "UserRole",
    [
        "id",
        "user_id",
        "role_id",
    ],
)

User = namedtuple(
    "User",
    [
        "id",
        "email",
        "hashed_password",
        "is_active",
        "is_superuser",
        "is_verified",
    ],
)
