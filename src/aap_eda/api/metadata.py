from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions, metadata
from rest_framework.request import clone_request


class EDAMetadata(metadata.SimpleMetadata):
    """Overwritten to show PATCH in OPTIONS."""

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
                actions[method] = self.get_serializer_info(serializer)
            finally:
                view.request = request

        return actions
