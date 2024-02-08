from ansible_base.lib.abstract_models import AbstractTeam
from django.db import models


class Team(AbstractTeam):
    organization = models.ForeignKey(
        "Organization", on_delete=models.CASCADE, null=True
    )
