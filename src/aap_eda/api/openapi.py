from django.conf import settings
from drf_spectacular.authentication import SessionScheme as _SessionScheme


def preprocess_filter_api_routes(endpoints):
    api_path = f"/{settings.API_PREFIX}"
    return [
        (path, path_regex, method, callback)
        for path, path_regex, method, callback in endpoints
        if path.startswith(api_path)
    ]


class SessionScheme(_SessionScheme):
    target_class = "aap_eda.api.authentication.SessionAuthentication"
