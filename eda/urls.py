from django.urls import include, path

from . import api_urls

from . import views


urlpatterns = []

urlpatterns += api_urls.urlpatterns

urlpatterns += [
    path("", views.index, name="index"),
    path("<str:room_name>/", views.room, name="room"),
]

__all__ = ["urlpatterns"]



