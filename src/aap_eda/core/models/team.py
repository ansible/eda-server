from ansible_base.lib.abstract_models import AbstractTeam


class Team(AbstractTeam):
    class Meta(AbstractTeam.Meta):
        app_label = "core"
        permissions = [
            ("member_team", "Inherit all roles assigned to this team")
        ]
