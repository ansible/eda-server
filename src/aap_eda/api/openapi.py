from django.conf import settings


def preprocess_filter_api_routes(endpoints):
    api_path = f"/{settings.API_PREFIX}/api/"
    return [
        (path, path_regex, method, callback)
        for path, path_regex, method, callback in endpoints
        if path.startswith(api_path)
    ]
