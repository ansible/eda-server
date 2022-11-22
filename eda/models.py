from django.db import models


class AlembicVersion(models.Model):

    version_num = models.AutoField(
        primary_key=True,
        max_length=32,
    )


class ActivationInstanceJobInstance(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    activation_instance_id = models.IntegerField(
        "ActivationInstance",
    )
    job_instance_id = models.IntegerField(
        "JobInstance",
    )


class ActivationInstance(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    name = models.CharField(blank=True)
    rulebook_id = models.IntegerField(
        "Rulebook",
    )
    inventory_id = models.IntegerField(
        "Inventory",
    )
    extra_var_id = models.IntegerField(
        "ExtraVar",
    )
    execution_environment = models.CharField(blank=True)
    working_directory = models.CharField(blank=True)
    large_data_id = models.OID()
    project_id = models.IntegerField(
        "Project",
    )


class ExtraVar(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    name = models.CharField(blank=True)
    extra_var = models.CharField(blank=True)
    project_id = models.IntegerField(
        "Project",
    )


class Project(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    git_hash = models.CharField(blank=True)
    url = models.CharField(blank=True)
    name = models.CharField(blank=True)
    description = models.CharField(blank=True)
    created_at = models.DateTimeField()
    modified_at = models.DateTimeField()
    large_data_id = models.OID()


class Inventory(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    name = models.CharField(blank=True)
    inventory = models.CharField(blank=True)
    project_id = models.IntegerField(
        "Project",
    )


class Rulebook(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    name = models.CharField(blank=True)
    rulesets = models.CharField(blank=True)
    project_id = models.IntegerField(
        "Project",
    )
    description = models.CharField(blank=True)
    created_at = models.DateTimeField()
    modified_at = models.DateTimeField()


class JobInstance(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    uuid = models.UUIDField()


class ActivationInstanceLog(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    activation_instance_id = models.IntegerField(
        "ActivationInstance",
    )
    line_number = models.IntegerField()
    log = models.CharField(blank=True)


class Rule(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    ruleset_id = models.IntegerField(
        "Ruleset",
    )
    name = models.CharField(blank=True)
    action = models.JSONField()


class Ruleset(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    rulebook_id = models.IntegerField(
        "Rulebook",
    )
    name = models.CharField(blank=True)
    created_at = models.DateTimeField()
    modified_at = models.DateTimeField()


class Job(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    uuid = models.UUIDField()


class Playbook(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    name = models.CharField(blank=True)
    playbook = models.CharField(blank=True)
    project_id = models.IntegerField(
        "Project",
    )


class AuditRule(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    name = models.CharField(blank=True)
    description = models.CharField(blank=True)
    status = models.CharField(blank=True)
    fired_date = models.DateTimeField()
    created_at = models.DateTimeField()
    definition = models.JSONField()
    rule_id = models.IntegerField(
        "Rule",
    )
    ruleset_id = models.IntegerField(
        "Ruleset",
    )
    activation_instance_id = models.IntegerField(
        "ActivationInstance",
    )
    job_instance_id = models.IntegerField(
        "JobInstance",
    )


class JobInstanceEvent(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    job_uuid = models.UUIDField()
    counter = models.IntegerField()
    stdout = models.CharField(blank=True)
    type = models.CharField(blank=True)
    created_at = models.DateTimeField()


class JobInstanceHost(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    host = models.CharField(blank=True)
    job_uuid = models.UUIDField()
    playbook = models.CharField(blank=True)
    play = models.CharField(blank=True)
    task = models.CharField(blank=True)
    status = models.CharField(blank=True)


class Activation(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    name = models.CharField(blank=True)
    rulebook_id = models.IntegerField(
        "Rulebook",
    )
    inventory_id = models.IntegerField(
        "Inventory",
    )
    extra_var_id = models.IntegerField(
        "ExtraVar",
    )
    description = models.CharField(blank=True)
    status = models.CharField(blank=True)
    is_enabled = models.BooleanField()
    restarted_at = models.DateTimeField()
    restart_count = models.IntegerField()
    created_at = models.DateTimeField()
    modified_at = models.DateTimeField()
    working_directory = models.CharField(blank=True)
    execution_environment = models.CharField(max_length=6, blank=True)
    restart_policy = models.CharField(max_length=10, blank=True)


class Role(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    name = models.CharField(blank=True)
    description = models.CharField(blank=True)


class RolePermission(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    role_id = models.UUIDField(
        "Role",
    )
    resource_type = models.CharField(max_length=13, blank=True)
    action = models.CharField(max_length=6, blank=True)


class UserRole(models.Model):

    user_id = models.AutoField(
        "User",
        primary_key=True,
    )
    role_id = models.AutoField(
        "Role",
        primary_key=True,
    )


class User(models.Model):

    email = models.CharField(max_length=320, blank=True)
    hashed_password = models.CharField(max_length=1024, blank=True)
    is_active = models.BooleanField()
    is_superuser = models.BooleanField()
    is_verified = models.BooleanField()
    id = models.AutoField(
        primary_key=True,
    )
