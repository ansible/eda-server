"""Signal handlers for EDA services."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from aap_eda.core import enums, models
from aap_eda.core.exceptions import GatewayAPIError, MissingCredentialsError
from aap_eda.services.sync_certs import SyncCertificates


@receiver(post_save, sender=models.EdaCredential)
def gw_handler(
    sender: type[models.EdaCredential],
    instance: models.EdaCredential,
    **kwargs,
) -> None:
    """Handle updates to EdaCredential object and force a certificate sync."""
    if (
        instance.credential_type is not None
        and instance.credential_type.name
        == enums.EventStreamCredentialType.MTLS
        and hasattr(instance, "_request")
    ):
        try:
            objects = models.EventStream.objects.filter(
                eda_credential_id=instance.id
            )
            if len(objects) > 0:
                SyncCertificates(instance.id).update()
        except (GatewayAPIError, MissingCredentialsError) as ex:
            from aap_eda.services import sync_certs

            sync_certs.LOGGER.error(
                "Couldn't trigger gateway certificate updates %s", str(ex)
            )
