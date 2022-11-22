from django.contrib import admin

from eda.models import ActivationInstanceJobInstance

from eda.models import ActivationInstance

from eda.models import ExtraVar

from eda.models import Project

from eda.models import Inventory

from eda.models import Rulebook

from eda.models import JobInstance

from eda.models import ActivationInstanceLog

from eda.models import Rule

from eda.models import Ruleset

from eda.models import Job

from eda.models import Playbook

from eda.models import AuditRule

from eda.models import JobInstanceEvent

from eda.models import JobInstanceHost

from eda.models import Activation

from eda.models import Role

from eda.models import RolePermission

from eda.models import UserRole

from eda.models import User


class ActivationInstanceJobInstanceAdmin(admin.ModelAdmin):
    fields = (
        "activation_instance_id",
        "job_instance_id",
    )
    raw_id_fields = (
        "activation_instance_id",
        "job_instance_id",
    )


admin.site.register(ActivationInstanceJobInstance, ActivationInstanceJobInstanceAdmin)


class ActivationInstanceAdmin(admin.ModelAdmin):
    fields = (
        "name",
        "rulebook_id",
        "inventory_id",
        "extra_var_id",
        "execution_environment",
        "working_directory",
        "project_id",
    )
    raw_id_fields = (
        "rulebook_id",
        "inventory_id",
        "extra_var_id",
        "project_id",
    )


admin.site.register(ActivationInstance, ActivationInstanceAdmin)


class ExtraVarAdmin(admin.ModelAdmin):
    fields = (
        "name",
        "extra_var",
        "project_id",
    )
    raw_id_fields = ("project_id",)


admin.site.register(ExtraVar, ExtraVarAdmin)


class ProjectAdmin(admin.ModelAdmin):
    fields = (
        "git_hash",
        "url",
        "name",
        "description",
        "created_at",
        "modified_at",
    )
    raw_id_fields = ()


admin.site.register(Project, ProjectAdmin)


class InventoryAdmin(admin.ModelAdmin):
    fields = (
        "name",
        "inventory",
        "project_id",
    )
    raw_id_fields = ("project_id",)


admin.site.register(Inventory, InventoryAdmin)


class RulebookAdmin(admin.ModelAdmin):
    fields = (
        "name",
        "rulesets",
        "project_id",
        "description",
        "created_at",
        "modified_at",
    )
    raw_id_fields = ("project_id",)


admin.site.register(Rulebook, RulebookAdmin)


class JobInstanceAdmin(admin.ModelAdmin):
    fields = ("uuid",)
    raw_id_fields = ()


admin.site.register(JobInstance, JobInstanceAdmin)


class ActivationInstanceLogAdmin(admin.ModelAdmin):
    fields = (
        "activation_instance_id",
        "line_number",
        "log",
    )
    raw_id_fields = ("activation_instance_id",)


admin.site.register(ActivationInstanceLog, ActivationInstanceLogAdmin)


class RuleAdmin(admin.ModelAdmin):
    fields = (
        "ruleset_id",
        "name",
        "action",
    )
    raw_id_fields = ("ruleset_id",)


admin.site.register(Rule, RuleAdmin)


class RulesetAdmin(admin.ModelAdmin):
    fields = (
        "rulebook_id",
        "name",
        "created_at",
        "modified_at",
    )
    raw_id_fields = ("rulebook_id",)


admin.site.register(Ruleset, RulesetAdmin)


class JobAdmin(admin.ModelAdmin):
    fields = ("uuid",)
    raw_id_fields = ()


admin.site.register(Job, JobAdmin)


class PlaybookAdmin(admin.ModelAdmin):
    fields = (
        "name",
        "playbook",
        "project_id",
    )
    raw_id_fields = ("project_id",)


admin.site.register(Playbook, PlaybookAdmin)


class AuditRuleAdmin(admin.ModelAdmin):
    fields = (
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
    )
    raw_id_fields = (
        "rule_id",
        "ruleset_id",
        "activation_instance_id",
        "job_instance_id",
    )


admin.site.register(AuditRule, AuditRuleAdmin)


class JobInstanceEventAdmin(admin.ModelAdmin):
    fields = (
        "job_uuid",
        "counter",
        "stdout",
        "type",
        "created_at",
    )
    raw_id_fields = ()


admin.site.register(JobInstanceEvent, JobInstanceEventAdmin)


class JobInstanceHostAdmin(admin.ModelAdmin):
    fields = (
        "host",
        "job_uuid",
        "playbook",
        "play",
        "task",
        "status",
    )
    raw_id_fields = ()


admin.site.register(JobInstanceHost, JobInstanceHostAdmin)


class ActivationAdmin(admin.ModelAdmin):
    fields = (
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
    )
    raw_id_fields = (
        "rulebook_id",
        "inventory_id",
        "extra_var_id",
    )


admin.site.register(Activation, ActivationAdmin)


class RoleAdmin(admin.ModelAdmin):
    fields = (
        "name",
        "description",
    )
    raw_id_fields = ()


admin.site.register(Role, RoleAdmin)


class RolePermissionAdmin(admin.ModelAdmin):
    fields = (
        "role_id",
        "resource_type",
        "action",
    )
    raw_id_fields = ("role_id",)


admin.site.register(RolePermission, RolePermissionAdmin)


class UserRoleAdmin(admin.ModelAdmin):
    fields = (
        "user_id",
        "role_id",
    )
    raw_id_fields = (
        "user_id",
        "role_id",
    )


admin.site.register(UserRole, UserRoleAdmin)


class UserAdmin(admin.ModelAdmin):
    fields = (
        "email",
        "hashed_password",
        "is_active",
        "is_superuser",
        "is_verified",
    )
    raw_id_fields = ()


admin.site.register(User, UserAdmin)
