from django.db import models


class Project(models.Model):
    name = models.TextField()
    git_hash = models.TextField()
    url = models.TextField()
    description = models.TextField()
    created_at = models.DateTimeField()
    modified_at = models.DateTimeField()


class Playbook(models.Model):
    name = models.TextField()
    playbook = models.TextField()
    project = models.ForeignKey(
        Project,
        null=True,
        on_delete=models.CASCADE,
        db_constraint=False,
    )


class ExtraVar(models.Model):
    name = models.TextField()
    extra_var = models.TextField()
    project = models.ForeignKey(
        Project,
        null=True,
        on_delete=models.CASCADE,
        db_constraint=False,
    )
