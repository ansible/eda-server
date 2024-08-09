import logging

from django.core.management import BaseCommand, CommandError

from aap_eda.utils.external_logging import reconfigure_rsyslog

# logger = logging.getLogger("aap.eda.rsyslog_configurer")

class Command(BaseCommand):
    """
    Rsyslog Configurer
    Configures <settings.LOG_AGGREGATOR_RSYSLOGD_CONF_DIR>/rsyslog.conf with values from dynamic preferences (settings).
    """  # noqa

    help = "Launch the rsyslog_configurer, updates rsyslog.conf"

    def handle(self, *arg, **options):
        try:
            reconfigure_rsyslog(restart_rsyslogd=False)
        except Exception as e:
            # Log unanticipated exception in addition to writing to stderr to get timestamps and other metadata # noqa
            raise CommandError(
                f"Unhandled Exception in reconfigure_rsyslog: {str(e)}"
            )
