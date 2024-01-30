from ansible_base.lib.channels.middleware import DrfAuthMiddlewareStack
from channels.routing import URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.conf import settings
from django.urls import path

from . import consumers

wsapi_router = URLRouter(
    [path("ansible-rulebook", consumers.AnsibleRulebookConsumer.as_asgi())]
)

wsapi_router = URLRouter(
    [
        path(f"{settings.API_PREFIX}/ws/", wsapi_router),
    ]
)

router = AllowedHostsOriginValidator(DrfAuthMiddlewareStack(wsapi_router))
