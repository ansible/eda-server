from django.apps import AppConfig

from aap_eda.utils.external_logging import reconfigure_rsyslog


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "aap_eda.api"

    reconfigure_rsyslog()
