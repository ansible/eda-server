from django.conf import settings


def preprocess_filter_api_routes(endpoints):
    api_path = f"/api/{settings.API_PREFIX}"
    return [
        (path, path_regex, method, callback)
        for path, path_regex, method, callback in endpoints
        if path.startswith(api_path)
    ]
