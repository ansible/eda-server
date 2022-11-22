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
    activation_instance_id = models.ForeignKey(
        "ActivationInstance", on_delete=models.CASCADE
    )
    job_instance_id = models.ForeignKey("JobInstance", on_delete=models.CASCADE)


class ActivationInstance(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    name = models.TextField()
    rulebook_id = models.ForeignKey("Rulebook", on_delete=models.CASCADE)
    inventory_id = models.ForeignKey("Inventory", on_delete=models.CASCADE)
    extra_var_id = models.ForeignKey("ExtraVar", on_delete=models.CASCADE)
    execution_environment = models.TextField()
    working_directory = models.TextField()
    #large_data_id = models.OID()
    project_id = models.ForeignKey("Project", on_delete=models.CASCADE)


class ExtraVar(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    name = models.TextField()
    extra_var = models.TextField()
    project_id = models.ForeignKey("Project", on_delete=models.CASCADE)


class Project(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    git_hash = models.TextField()
    url = models.TextField()
    name = models.TextField()
    description = models.TextField()
    created_at = models.DateTimeField()
    modified_at = models.DateTimeField()
    #large_data_id = models.OID()


class Inventory(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    name = models.TextField()
    inventory = models.TextField()
    project_id = models.ForeignKey("Project", on_delete=models.CASCADE)


class Rulebook(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    name = models.TextField()
    rulesets = models.TextField()
    project_id = models.ForeignKey("Project", on_delete=models.CASCADE)
    description = models.TextField()
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
    activation_instance_id = models.ForeignKey(
        "ActivationInstance", on_delete=models.CASCADE
    )
    line_number = models.IntegerField()
    log = models.TextField()


class Rule(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    ruleset_id = models.ForeignKey("Ruleset", on_delete=models.CASCADE)
    name = models.TextField()
    action = models.JSONField()


class Ruleset(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    rulebook_id = models.ForeignKey("Rulebook", on_delete=models.CASCADE)
    name = models.TextField()
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
    name = models.TextField()
    playbook = models.TextField()
    project_id = models.ForeignKey("Project", on_delete=models.CASCADE)


class AuditRule(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    name = models.TextField()
    description = models.TextField()
    status = models.TextField()
    fired_date = models.DateTimeField()
    created_at = models.DateTimeField()
    definition = models.JSONField()
    rule_id = models.ForeignKey("Rule", on_delete=models.CASCADE)
    ruleset_id = models.ForeignKey("Ruleset", on_delete=models.CASCADE)
    activation_instance_id = models.ForeignKey(
        "ActivationInstance", on_delete=models.CASCADE
    )
    job_instance_id = models.ForeignKey("JobInstance", on_delete=models.CASCADE)


class JobInstanceEvent(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    job_uuid = models.UUIDField()
    counter = models.IntegerField()
    stdout = models.TextField()
    type = models.TextField()
    created_at = models.DateTimeField()


class JobInstanceHost(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    host = models.TextField()
    job_uuid = models.UUIDField()
    playbook = models.TextField()
    play = models.TextField()
    task = models.TextField()
    status = models.TextField()


class Activation(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    name = models.TextField()
    rulebook_id = models.ForeignKey("Rulebook", on_delete=models.CASCADE)
    inventory_id = models.ForeignKey("Inventory", on_delete=models.CASCADE)
    extra_var_id = models.ForeignKey("ExtraVar", on_delete=models.CASCADE)
    description = models.TextField()
    status = models.TextField()
    is_enabled = models.BooleanField()
    restarted_at = models.DateTimeField()
    restart_count = models.IntegerField()
    created_at = models.DateTimeField()
    modified_at = models.DateTimeField()
    working_directory = models.TextField()
    execution_environment = models.TextField(
        max_length=6,
    )
    restart_policy = models.TextField(
        max_length=10,
    )


class Role(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    name = models.TextField()
    description = models.TextField()


class RolePermission(models.Model):

    id = models.AutoField(
        primary_key=True,
    )
    role_id = models.ForeignKey("Role", on_delete=models.CASCADE)
    resource_type = models.TextField(
        max_length=13,
    )
    action = models.TextField(
        max_length=6,
    )


class UserRole(models.Model):

    user_id = models.ForeignKey("User", on_delete=models.CASCADE)
    role_id = models.ForeignKey("Role", on_delete=models.CASCADE)
    id = models.AutoField(
        primary_key=True,
    )


class User(models.Model):

    email = models.TextField(
        max_length=320,
    )
    hashed_password = models.TextField(
        max_length=1024,
    )
    is_active = models.BooleanField()
    is_superuser = models.BooleanField()
    is_verified = models.BooleanField()
    id = models.AutoField(
        primary_key=True,
    )
