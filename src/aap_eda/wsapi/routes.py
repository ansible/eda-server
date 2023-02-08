from channels.routing import URLRouter
from django.conf import settings
from django.urls import path

from . import consumers

wsapi_router = URLRouter([path("echo", consumers.EchoConsumer.as_asgi())])
wsapi2_router = URLRouter(
    [path("ws2", consumers.AnsibleRulebookConsumer.as_asgi())]
)

router = URLRouter(
    [
        path(f"{settings.API_PREFIX}/ws-api/", wsapi_router),
        path(f"{settings.API_PREFIX}/", wsapi2_router),
    ]
)
