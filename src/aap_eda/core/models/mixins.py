from django.utils import timezone


class ModifiedAtUpdaterMixin:
    """Mixin to ensure that the `modified_at` field is updated.

    Ensure that the `modified_at` field is updated when the model
    is saved with specific fields (`update_fields`) specified for update.
    Only works for `auto_now` fields.
    """

    def save(self, *args, **kwargs):
        for field in self._meta.fields:
            if (
                field.name == "modified_at"
                and hasattr(field, "auto_now")
                and field.auto_now
                and kwargs.get("update_fields", [])
            ):
                self.modified_at = timezone.now()
        super().save(*args, **kwargs)
