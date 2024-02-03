from ansible_base.lib.channels.middleware import DrfAuthMiddlewareStack
from channels.routing import URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.conf import settings
from django.urls import path, re_path

from . import consumers

default_path = re_path(r".*/?$", consumers.DefaultConsumer.as_asgi())


default_router = URLRouter(
    [
        default_path,
    ],
)

wsapi_router = URLRouter(
    [
        path("ansible-rulebook", consumers.AnsibleRulebookConsumer.as_asgi()),
        default_path,
    ],
)

wsapi_router = URLRouter(
    [
        path(f"{settings.API_PREFIX}/ws/", wsapi_router),
        path("", default_router),
    ],
)

router = AllowedHostsOriginValidator(DrfAuthMiddlewareStack(wsapi_router))
