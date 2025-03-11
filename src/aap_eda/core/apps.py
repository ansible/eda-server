from django.apps import AppConfig

from dispatcher.config import setup as dispatcher_setup


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "aap_eda.core"

    def ready(self):
        # make sure we apply DAB decorations in case they are not yet imported
        from aap_eda.api.views import dab_decorate  # noqa: F401

        from django.conf import settings

        dispatcher_setup(
            {
                "version": 2,
                "service": {
                    "pool_kwargs": {
                        "min_workers": settings.DISPATCHERD_MIN_WORKERS,
                        "max_workers": settings.DISPATCHERD_MAX_WORKERS,
                    },
                    "process_manager_cls": "ForkServerManager",
                    "process_manager_kwargs": {"preload_modules": ['aap_eda.core.tasking.hazmat']},
                },
                "brokers": {
                    "pg_notify": {
                        "config": {"conninfo": settings.PG_NOTIFY_DSN_SERVER},
                        "sync_connection_factory": "aap_eda.utils.db.psycopg_connection_from_django",
                        # Channels are only valid if this is a general worker
                        "channels": ["eda_workers"],
                        "default_publish_channel": "default",  # for web service submitting a task
                    }
                },
                "producers": {},  # tasks are only ran by the eda workers
                "publish": {"default_broker": "pg_notify"},
            }
        )
