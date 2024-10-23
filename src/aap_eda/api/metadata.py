from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.utils.encoding import force_str
from rest_framework import exceptions, metadata
from rest_framework.request import clone_request

ADDITIONAL_ATTRS = [
    "min_length",
    "max_length",
    "min_value",
    "max_value",
    "category",
    "category_slug",
    "defined_in_file",
    "unit",
    "hidden",
    "default",
]


class EDAMetadata(metadata.SimpleMetadata):
    """Overwritten to show PATCH in OPTIONS and add more attributes."""

    def get_field_info(self, field):
        field_info = super().get_field_info(field)

        for attr in ADDITIONAL_ATTRS:
            value = getattr(field, attr, None)
            if value is not None and value != "":
                field_info[attr] = force_str(value, strings_only=True)
        return field_info

    def determine_actions(self, request, view):
        """For generic class based views we return information about.

        the fields that are accepted for 'PUT' and 'POST' methods.
        """
        actions = {}
        for method in {"GET", "PUT", "PATCH", "POST"} & set(
            view.allowed_methods
        ):
            view.request = clone_request(request, method)
            try:
                # Test global permissions
                if hasattr(view, "check_permissions"):
                    view.check_permissions(view.request)
                # Test object permissions
                if method in ("PUT", "PATCH") and hasattr(view, "get_object"):
                    view.get_object()
            except (exceptions.APIException, PermissionDenied, Http404):
                pass
            else:
                # If user has appropriate permissions for the view, include
                # appropriate metadata about the fields that should be supplied
                serializer = view.get_serializer()
                action = self.get_serializer_info(serializer)
                EDAMetadata._customize_field_attributes(method, action)
                actions[method] = action
            finally:
                view.request = request

        return actions

    @staticmethod
    def _customize_field_attributes(method: str, action: dict):
        for field, meta in list(action.items()):
            if not isinstance(meta, dict):
                continue

            # For GET method, remove meta attributes that aren't relevant
            # when reading a field and remove write-only fields.
            if method == "GET":
                attrs_to_remove = (
                    "required",
                    "read_only",
                    "default",
                    "min_length",
                    "max_length",
                )
                for attr in attrs_to_remove:
                    meta.pop(attr, None)
                if meta.pop("write_only", False):
                    action.pop(field)

            # For PUT/PATCH/POST methods, remove read-only fields.
            if method in ("PUT", "PATCH", "POST"):
                # file-based read-only settings can't be updated
                meta.pop("defined_in_file", False)

                if meta.pop("read_only", False):
                    action.pop(field)
