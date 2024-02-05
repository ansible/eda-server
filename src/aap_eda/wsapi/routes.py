from ansible_base.lib.channels.middleware import DrfAuthMiddlewareStack
from channels.routing import URLRouter
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

router = DrfAuthMiddlewareStack(wsapi_router)
