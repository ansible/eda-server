from channels.routing import URLRouter
from django.conf import settings
from django.urls import path

from . import consumers

wsapi_router = URLRouter([path("ansible-rulebook", consumers.AnsibleRulebookConsumer.as_asgi())])

router = URLRouter(
    [
        path(f"{settings.API_PREFIX}/ws/", wsapi_router),
    ]
)
