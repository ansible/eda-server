from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.utils.encoding import force_str
from rest_framework import exceptions, metadata
from rest_framework.request import clone_request

from aap_eda.api.validation_patterns import (
    inject_top_level_clean_text_patterns,
)

# Map HTTP methods to the DRF action names that routers assign, so
# get_serializer_class() overrides that dispatch on ``self.action``
# return the correct (write) serializer during OPTIONS metadata
# generation.  See ``determine_actions`` below.
_METHOD_ACTION_MAP = {
    "GET": "list",
    "POST": "create",
    "PUT": "update",
    "PATCH": "partial_update",
}

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

        # Advertise CleanTextMixin Tier 1/Tier 2 patterns on
        # top-level CharFields (AAP-87587).  No-op unless
        # ENHANCED_INPUT_VALIDATION_ENABLED is on and the
        # serializer mixes in CleanTextMixin.
        field_info = inject_top_level_clean_text_patterns(field, field_info)

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
        original_action = getattr(view, "action", None)
        for method in {"GET", "PUT", "PATCH", "POST"} & set(
            view.allowed_methods
        ):
            view.request = clone_request(request, method)

            # Set view.action so that get_serializer_class() overrides
            # which dispatch on self.action (rather than
            # self.request.method) return the correct write serializer.
            # Prefer the view's own action_map when available (it
            # carries the router-assigned action names); fall back to
            # the static mapping for views without one.
            action_map = getattr(view, "action_map", None)
            if action_map:
                view.action = action_map.get(
                    method.lower(),
                    _METHOD_ACTION_MAP.get(method, method.lower()),
                )
            else:
                view.action = _METHOD_ACTION_MAP.get(method, method.lower())

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
                # appropriate metadata about the fields that should be
                # supplied.
                serializer = view.get_serializer()
                action = self.get_serializer_info(serializer)
                EDAMetadata._customize_field_attributes(method, action)
                actions[method] = action
            finally:
                view.request = request

        view.action = original_action
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
            elif method in ("PUT", "PATCH", "POST"):
                # file-based read-only settings can't be updated
                meta.pop("defined_in_file", False)

                if meta.pop("read_only", False):
                    action.pop(field)
